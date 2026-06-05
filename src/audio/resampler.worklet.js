// AudioWorklet：把麦克风音频（context 采样率）线性重采样到 16kHz，
// 累积成正好 512 个 16-bit PCM 样本的帧，通过 port 上行给 audio.ts。
class ResamplerProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    // sampleRate 是 worklet 全局作用域里的 context 采样率（通常 48000/44100）。
    this._ratio = sampleRate / 16000
    this._pending = []
    this._pos = 0
    this._out = []
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || !input[0]) return true
    const ch = input[0]
    for (let i = 0; i < ch.length; i++) this._pending.push(ch[i])

    while (Math.ceil(this._pos) < this._pending.length) {
      const idx = Math.floor(this._pos)
      const frac = this._pos - idx
      const a = this._pending[idx]
      const b = this._pending[idx + 1] !== undefined ? this._pending[idx + 1] : a
      this._out.push(a * (1 - frac) + b * frac)
      this._pos += this._ratio

      if (this._out.length === 512) {
        const frame = new Int16Array(512)
        for (let j = 0; j < 512; j++) {
          let s = Math.round(this._out[j] * 32768)
          if (s > 32767) s = 32767
          else if (s < -32768) s = -32768
          frame[j] = s
        }
        this.port.postMessage(frame.buffer, [frame.buffer])
        this._out = []
      }
    }

    const consumed = Math.floor(this._pos)
    if (consumed > 0) {
      this._pending.splice(0, consumed)
      this._pos -= consumed
    }
    return true
  }
}

registerProcessor('resampler', ResamplerProcessor)
