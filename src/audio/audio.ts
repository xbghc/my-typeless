// 隐藏音频 worker renderer：getUserMedia → AudioWorklet 重采样 → Silero VAD 分段 → WAV 段上行。
// 对应旧版 recorder.py + vad.py。
import * as ort from 'onnxruntime-web/wasm'
import workletUrl from './resampler.worklet.js?url'
import { computeRms } from './level'

ort.env.wasm.numThreads = 1

const FRAME = 512
const SAMPLE_RATE = 16000
const SPEECH_THRESHOLD = 0.5
// 整型截断（与旧版 int() 一致）：0.6s 静音触发分段，最短语音 0.5s。
const SILENCE_CHUNKS = Math.trunc((0.6 * SAMPLE_RATE) / FRAME) // 18
const MIN_SPEECH_CHUNKS = Math.trunc((0.5 * SAMPLE_RATE) / FRAME) // 15

let session: ort.InferenceSession | null = null
let vadState: ort.Tensor
const srTensor = new ort.Tensor('int64', BigInt64Array.from([16000n]), [])

function resetVad(): void {
  vadState = new ort.Tensor('float32', new Float32Array(2 * 1 * 128), [2, 1, 128])
}

async function ensureSession(): Promise<void> {
  if (session) return
  // ort 的 wasm/mjs 经 IPC 取字节，用 blob URL 提供（dev http 与打包 file:// 都同源可用）。
  const { wasm, mjs } = await window.audioApi.getOrtAssets()
  ort.env.wasm.wasmPaths = {
    wasm: URL.createObjectURL(new Blob([wasm], { type: 'application/wasm' })),
    mjs: URL.createObjectURL(new Blob([mjs], { type: 'text/javascript' })),
  }
  const model = await window.audioApi.getVadModel()
  session = await ort.InferenceSession.create(model, { executionProviders: ['wasm'] })
  resetVad()
}

async function vadProbability(frame: Int16Array): Promise<number> {
  const data = new Float32Array(FRAME)
  for (let i = 0; i < FRAME; i++) data[i] = frame[i] / 32768
  const input = new ort.Tensor('float32', data, [1, FRAME])
  const results = await session!.run({ input, state: vadState, sr: srTensor })
  const names = session!.outputNames
  vadState = results[names[1]] as ort.Tensor
  return (results[names[0]].data as Float32Array)[0]
}

// ── 分段状态机（逐字对应 recorder._record_loop）──
let recording = false
let segmentFrames: Int16Array[] = []
let inSpeech = false
let silenceCount = 0

// 音量电平节流：worklet ~31fps，每 LEVEL_EVERY 帧推一次（~16Hz），取窗口内最大 RMS，供 overlay 波形。
const LEVEL_EVERY = 2
let levelCounter = 0
let levelPeak = 0

let stream: MediaStream | null = null
let audioCtx: AudioContext | null = null
let sourceNode: MediaStreamAudioSourceNode | null = null
let workletNode: AudioWorkletNode | null = null
// onFrame 是异步（await VAD 推理）。worklet 的帧通过 promise 链串行处理，
// 避免推理慢于帧率时多个 onFrame 并发读写 vadState/segmentFrames（旧版单线程循环天然串行）。
let frameChain: Promise<void> = Promise.resolve()

async function onFrame(frame: Int16Array): Promise<void> {
  if (!recording || !session) return
  segmentFrames.push(frame)
  // 音量电平节流推送，供 overlay 波形（main 端按录音态门控转发）。
  const rms = computeRms(frame)
  if (rms > levelPeak) levelPeak = rms
  if (++levelCounter >= LEVEL_EVERY) {
    window.audioApi.sendLevel(levelPeak)
    levelCounter = 0
    levelPeak = 0
  }
  const prob = await vadProbability(frame)
  if (prob >= SPEECH_THRESHOLD) {
    inSpeech = true
    silenceCount = 0
  } else {
    silenceCount++
    if (inSpeech && silenceCount >= SILENCE_CHUNKS) {
      const speechEnd = segmentFrames.length - silenceCount
      if (speechEnd >= MIN_SPEECH_CHUNKS) {
        window.audioApi.sendSegment(buildWav(segmentFrames.slice(0, speechEnd)))
      }
      // 保留尾部静音帧作为下一段起始缓冲。
      segmentFrames = segmentFrames.slice(-silenceCount)
      inSpeech = false
      silenceCount = 0
    }
  }
}

async function start(): Promise<void> {
  if (recording) return
  try {
    await ensureSession()
    resetVad()
    segmentFrames = []
    inSpeech = false
    silenceCount = 0
    levelCounter = 0
    levelPeak = 0
    frameChain = Promise.resolve()
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })
    audioCtx = new AudioContext()
    await audioCtx.audioWorklet.addModule(workletUrl)
    sourceNode = audioCtx.createMediaStreamSource(stream)
    workletNode = new AudioWorkletNode(audioCtx, 'resampler')
    workletNode.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
      const frame = new Int16Array(e.data)
      // 串行化处理并吞掉单帧错误，保证 stop() 中 `await frameChain` 不会因某帧 reject 而中断。
      frameChain = frameChain.then(() => onFrame(frame)).catch(() => {})
    }
    sourceNode.connect(workletNode)
    recording = true
  } catch (e) {
    window.audioApi.sendError(e instanceof Error ? e.message : String(e))
  }
}

async function stop(): Promise<void> {
  if (!recording) return
  // 先断开音频输入停止产生新帧，但保持 recording=true 让已入队的帧处理完，
  // 对齐旧版 recorder.stop 的 thread.join，避免丢失录音末尾积压的帧。
  try {
    sourceNode?.disconnect()
    workletNode?.disconnect()
  } catch {
    // ignore
  }
  await frameChain
  recording = false
  // 增量模式：发送尚未通过停顿回调发出的剩余音频作为末段。
  if (segmentFrames.length > 0) {
    window.audioApi.sendSegment(buildWav(segmentFrames))
  }
  segmentFrames = []
  window.audioApi.sendEnd()
  try {
    stream?.getTracks().forEach((t) => t.stop())
    await audioCtx?.close()
  } catch {
    // ignore
  }
  stream = null
  audioCtx = null
  sourceNode = null
  workletNode = null
}

function buildWav(frames: Int16Array[]): ArrayBuffer {
  const total = frames.reduce((n, f) => n + f.length, 0)
  const dataBytes = total * 2
  const buf = new ArrayBuffer(44 + dataBytes)
  const view = new DataView(buf)
  const writeStr = (off: number, s: string): void => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i))
  }
  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + dataBytes, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, SAMPLE_RATE, true)
  view.setUint32(28, SAMPLE_RATE * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeStr(36, 'data')
  view.setUint32(40, dataBytes, true)
  let off = 44
  for (const f of frames) {
    for (let i = 0; i < f.length; i++) {
      view.setInt16(off, f[i], true)
      off += 2
    }
  }
  return buf
}

window.audioApi.onStart(() => void start())
window.audioApi.onStop(() => void stop())

// 预加载 VAD session：验证 ort wasm + 模型可加载，并降低首次录音延迟。
void ensureSession()
  .then(() => console.log(`VAD session ready, inputs=${session?.inputNames.join(',')}`))
  .catch((e) => console.error(`VAD session failed: ${e instanceof Error ? e.message : String(e)}`))
console.log('worker ready')
