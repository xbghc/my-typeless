// preload 暴露给 renderer 的 API 契约（main/preload/renderer 共用）。
import type {
  AppConfig,
  AppState,
  Candidate,
  ErrorPayload,
  HistoryPage,
  OverlayTheme,
  PlaygroundResult,
  ProviderTestPayload,
  SaveResult,
  TestResult,
} from './types'

export interface Api {
  // 配置
  getConfig(): Promise<AppConfig>
  saveConfig(data: AppConfig): Promise<SaveResult>
  // 历史
  getHistory(offset: number, limit: number): Promise<HistoryPage>
  clearHistory(): Promise<{ success: boolean }>
  // Playground / 连接测试
  runTest(rawText: string, llmOverride?: unknown): Promise<PlaygroundResult>
  testSttConnection(payload: ProviderTestPayload): Promise<TestResult>
  testLlmConnection(payload: ProviderTestPayload): Promise<TestResult>
  // 应用 / 热键
  getVersion(): Promise<string>
  getAllowedHotkeys(): Promise<string[]>
  startHotkeyCapture(): Promise<void>
  closeWindow(): Promise<void>
  // 术语候选
  getGlossaryCandidates(minCount?: number): Promise<Candidate[]>
  acceptGlossaryCandidate(term: string): Promise<{ success: boolean; error?: string }>
  dismissGlossaryCandidate(term: string): Promise<{ success: boolean; error?: string }>
  // 下行事件（返回取消订阅函数）
  onStateChanged(cb: (state: AppState) => void): () => void
  onErrorOccurred(cb: (payload: ErrorPayload) => void): () => void
  onHotkeyCaptured(cb: (key: string | null) => void): () => void
  onResultReady(cb: (text: string) => void): () => void
}

// 隐藏音频 worker renderer 使用的 API（window.audioApi）。
export interface AudioApi {
  getOrtAssets(): Promise<{ wasm: ArrayBuffer; mjs: ArrayBuffer }>
  getVadModel(): Promise<ArrayBuffer>
  onStart(cb: () => void): () => void
  onStop(cb: () => void): () => void
  sendSegment(wav: ArrayBuffer): void
  sendEnd(): void
  sendError(message: string): void
  // 录音音量电平（0..1），节流后上行给 main 转发到 overlay 做波形。
  sendLevel(level: number): void
}

// 反馈浮窗（src/overlay）使用的 API（window.overlayApi）。纯下行：状态 / 电平 / 主题。
export interface OverlayApi {
  onState(cb: (state: AppState) => void): () => void
  onLevel(cb: (level: number) => void): () => void
  onTheme(cb: (theme: OverlayTheme) => void): () => void
}
