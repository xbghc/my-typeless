// IPC 通道名的单一真源（main / preload / renderer 共用）。
export const IPC = {
  // 设置窗口 A ↔ main（invoke）
  CONFIG_GET: 'config:get',
  CONFIG_SAVE: 'config:save',
  HISTORY_GET: 'history:get',
  HISTORY_CLEAR: 'history:clear',
  PLAYGROUND_RUN: 'playground:run',
  STT_TEST: 'stt:test',
  LLM_TEST: 'llm:test',
  APP_VERSION: 'app:version',
  HOTKEY_ALLOWED: 'hotkey:allowed',
  HOTKEY_CAPTURE_START: 'hotkey:capture-start',
  WINDOW_CLOSE: 'window:close',
  CANDIDATES_GET: 'candidates:get',
  CANDIDATES_ACCEPT: 'candidates:accept',
  CANDIDATES_DISMISS: 'candidates:dismiss',

  // 录音控制 / 音频 main ↔ B
  AUDIO_ORT_ASSETS: 'audio:ort-assets',
  AUDIO_MODEL: 'audio:model',
  AUDIO_START: 'audio:start',
  AUDIO_STOP: 'audio:stop',
  AUDIO_SEGMENT: 'audio:segment',
  AUDIO_END: 'audio:end',
  AUDIO_ERROR: 'audio:error',

  // 事件下行 main → A
  STATE_CHANGED: 'state:changed',
  ERROR_OCCURRED: 'error:occurred',
  HOTKEY_CAPTURED: 'hotkey:captured',
  RESULT_READY: 'result:ready',
} as const

export type IpcChannel = (typeof IPC)[keyof typeof IPC]
