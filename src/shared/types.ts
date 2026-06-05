// 跨进程共享的核心类型。

export type AppState = 'idle' | 'recording' | 'processing'

export type ProviderType = 'openai' | 'anthropic'

export interface ProviderConfig {
  id: string
  name: string
  base_url: string
  api_key: string
  models: string[]
  provider_type: ProviderType
}

export interface STTConfig {
  providers: ProviderConfig[]
  active_provider_id: string
  active_model: string
  language: string
}

export interface LLMConfig {
  providers: ProviderConfig[]
  active_provider_id: string
  active_model: string
  prompt: string
}

export interface AppConfig {
  hotkey: string
  start_with_windows: boolean
  stt: STTConfig
  llm: LLMConfig
  glossary: string[]
}

export interface HistoryEntry {
  id?: number
  timestamp: string
  raw_input: string
  refined_output: string
  key_press_at: string | null
  key_release_at: string | null
  stt_done_at: string | null
  llm_done_at: string | null
}

export interface HistoryPage {
  entries: HistoryEntry[]
  has_more: boolean
  next_offset: number | null
}

// worker → history 的计时信息（驼峰命名，写库时映射到下划线列）。
export interface TimingInfo {
  keyPressAt?: string | null
  keyReleaseAt?: string | null
  sttDoneAt?: string | null
  llmDoneAt?: string | null
}

export interface Candidate {
  term: string
  count: number
  last_seen: string
  ignored: boolean
}

export interface SaveResult {
  success: boolean
  error?: string
}

export interface TestResult {
  success: boolean
  error?: string
}

export interface PlaygroundResult {
  success: boolean
  result?: string
  error?: string
}

// 连接测试 / Playground 传入的临时 provider 凭据
export interface ProviderTestPayload {
  base_url?: string
  api_key?: string
  model?: string
  provider_type?: ProviderType
}

export interface ErrorPayload {
  message: string
  critical: boolean
}
