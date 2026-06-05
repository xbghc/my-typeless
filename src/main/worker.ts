// 后台流水线：分段 STT（边录边转）→ 繁简 → 拼接 → 整段 LLM 精修一次 → 注入 → 历史 → 候选。
// 对应旧版 worker.py。纯函数与流水线可注入依赖，便于单测；运行时由 main 接 IPC 段流驱动。
import { Converter } from 'opencc-js'
import type { AppConfig, AppState, LLMConfig, STTConfig, TimingInfo } from '@shared/types'
import { buildLlmSystemPrompt, buildSttPrompt } from './config'
import { mapProcessingError } from './errorMap'
import { STTClient } from './sttClient'
import { LLMClient } from './llmClient'

// Whisper prompt 上限约 224 tokens；对中文约 400 字符，取尾部以保留最近上下文。
const MAX_PROMPT_CHARS = 400

export function updateTranscriptionTail(currentTail: string, newText: string, maxChars: number): string {
  if (maxChars <= 0) return ''
  const merged = `${currentTail}${newText}`
  return merged.slice(-maxChars)
}

export function buildSttPromptWithTail(tail: string, baseSttPrompt: string): string {
  if (baseSttPrompt) return tail ? `${tail} ${baseSttPrompt}` : baseSttPrompt
  return tail
}

let _converter: ((t: string) => string) | null = null
export function toSimplified(text: string): string {
  if (!_converter) _converter = Converter({ from: 'tw', to: 'cn' })
  return _converter(text)
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}
function nowTimeFmt(d = new Date()): string {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`
}

interface SttLike {
  transcribe(audio: Buffer, prompt?: string): Promise<string> | string
}
interface LlmLike {
  refine(text: string, systemPrompt?: string, context?: string): Promise<string> | string
}

export interface WorkerDeps {
  sttClientFactory?: (cfg: STTConfig) => SttLike
  llmClientFactory?: (cfg: LLMConfig) => LlmLike
  textInjector?: (text: string) => void | Promise<void>
  historyAdder?: (raw: string, refined: string, timing: TimingInfo) => void
  candidatesRecorder?: (refined: string, glossary: string[]) => void
  simplify?: (text: string) => string
  onStateChange?: (state: AppState) => void
  onResult?: (text: string) => void
  onError?: (message: string, critical: boolean) => void
}

// 运行时段流：main 收到 IPC audio:segment 时 push，audio:end 时 end。
export class SegmentQueue implements AsyncIterable<Buffer> {
  private items: Buffer[] = []
  private waiting: ((r: IteratorResult<Buffer>) => void) | null = null
  private ended = false

  push(buf: Buffer): void {
    if (this.ended) return
    if (this.waiting) {
      this.waiting({ value: buf, done: false })
      this.waiting = null
    } else {
      this.items.push(buf)
    }
  }

  end(): void {
    this.ended = true
    if (this.waiting) {
      this.waiting({ value: undefined as unknown as Buffer, done: true })
      this.waiting = null
    }
  }

  [Symbol.asyncIterator](): AsyncIterator<Buffer> {
    return {
      next: (): Promise<IteratorResult<Buffer>> => {
        if (this.items.length) {
          return Promise.resolve({ value: this.items.shift() as Buffer, done: false })
        }
        if (this.ended) {
          return Promise.resolve({ value: undefined as unknown as Buffer, done: true })
        }
        return new Promise((resolve) => {
          this.waiting = resolve
        })
      },
    }
  }
}

async function* toAsync(src: Buffer[] | AsyncIterable<Buffer>): AsyncIterable<Buffer> {
  if (Array.isArray(src)) {
    for (const s of src) yield s
  } else {
    for await (const s of src) yield s
  }
}

const noop = (): void => {}

export class Worker {
  private config: AppConfig
  private sttFactory: (cfg: STTConfig) => SttLike
  private llmFactory: (cfg: LLMConfig) => LlmLike
  private textInjector: (text: string) => void | Promise<void>
  private historyAdder: (raw: string, refined: string, timing: TimingInfo) => void
  private candidatesRecorder: (refined: string, glossary: string[]) => void
  private simplify: (text: string) => string
  private onStateChange: (state: AppState) => void
  private onResult: (text: string) => void
  private onError: (message: string, critical: boolean) => void

  // 运行时状态
  private queue: SegmentQueue | null = null
  private keyPressAt = ''
  private keyReleaseAt = ''
  private runPromise: Promise<void> | null = null
  // 从 startRecording 到流水线 finally 之间为 true；供 controller 判定重入与崩溃收尾。
  private running = false

  constructor(config: AppConfig, deps: WorkerDeps = {}) {
    this.config = config
    this.sttFactory = deps.sttClientFactory ?? ((cfg) => new STTClient(cfg))
    this.llmFactory = deps.llmClientFactory ?? ((cfg) => new LLMClient(cfg))
    this.textInjector = deps.textInjector ?? noop
    this.historyAdder = deps.historyAdder ?? noop
    this.candidatesRecorder = deps.candidatesRecorder ?? noop
    this.simplify = deps.simplify ?? toSimplified
    this.onStateChange = deps.onStateChange ?? noop
    this.onResult = deps.onResult ?? noop
    this.onError = deps.onError ?? noop
  }

  updateConfig(config: AppConfig): void {
    this.config = config
  }

  /** 是否有一段录音正在录制或处理中（用于忽略重入、判断是否需要崩溃收尾）。 */
  isRunning(): boolean {
    return this.running
  }

  // ── 运行时入口（由 main 的热键/音频 IPC 驱动）──
  startRecording(): void {
    this.running = true
    this.keyPressAt = nowTimeFmt()
    this.keyReleaseAt = ''
    this.queue = new SegmentQueue()
    this.onStateChange('recording')
    this.runPromise = this.incrementalProcess(this.keyPressAt, this.queue, () => this.keyReleaseAt)
  }

  pushSegment(wav: Buffer): void {
    this.queue?.push(wav)
  }

  stopRecording(): void {
    // 录音已被崩溃/错误路径提前收尾（running=false）时，忽略松键，避免又把状态切回 processing。
    if (!this.running) return
    this.keyReleaseAt = nowTimeFmt()
    this.onStateChange('processing')
  }

  finishSegments(): void {
    this.queue?.end()
  }

  /**
   * 录音中逐段 STT（边录边转），段流结束后对全文做一次 LLM 精修，再注入。
   * @param segmentSource 测试传 Buffer[]；运行时传段的 AsyncIterable（IPC 流）。
   * @param keyReleaseAt 字符串或 getter（运行时松键时刻在段流结束前已确定）。
   */
  async incrementalProcess(
    keyPressAt: string,
    segmentSource: Buffer[] | AsyncIterable<Buffer>,
    keyReleaseAt: string | (() => string) = '',
  ): Promise<void> {
    try {
      const stt = this.sttFactory(this.config.stt)
      const llm = this.llmFactory(this.config.llm)
      const baseSttPrompt = buildSttPrompt(this.config)
      const systemPrompt = buildLlmSystemPrompt(this.config)

      const parts: string[] = []
      let tail = ''
      const tailBudget = baseSttPrompt ? MAX_PROMPT_CHARS - baseSttPrompt.length - 1 : MAX_PROMPT_CHARS

      for await (const seg of toAsync(segmentSource)) {
        const sttPrompt = buildSttPromptWithTail(tail, baseSttPrompt)
        let text = await stt.transcribe(seg, sttPrompt)
        // Whisper 在 language="zh" 时仍常输出繁体，统一转简体（对非中文是 no-op）。
        text = this.simplify(text)
        if (!text || !text.trim()) continue
        parts.push(text)
        tail = updateTranscriptionTail(tail, text, tailBudget)
      }

      const sttDoneAt = nowTimeFmt()
      const rawText = parts.join('')
      if (!rawText.trim()) {
        this.onStateChange('idle')
        return
      }

      // 整段一次性精修：让 LLM 看到全文做跨段去重、统一列表序号等全局整理。
      const refined = await llm.refine(rawText, systemPrompt)
      const llmDoneAt = nowTimeFmt()

      await this.textInjector(refined)

      const releaseAt = typeof keyReleaseAt === 'function' ? keyReleaseAt() : keyReleaseAt
      this.historyAdder(rawText, refined, { keyPressAt, keyReleaseAt: releaseAt, sttDoneAt, llmDoneAt })

      // 候选记录失败不应中断主流程。
      try {
        this.candidatesRecorder(refined, this.config.glossary)
      } catch (e) {
        console.error('Failed to record glossary candidates:', e)
      }

      this.onResult(refined)
    } catch (e) {
      const { message, critical } = mapProcessingError(e)
      this.onError(message, critical)
    } finally {
      this.running = false
      this.onStateChange('idle')
    }
  }
}
