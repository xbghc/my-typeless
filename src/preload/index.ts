import { contextBridge, ipcRenderer, type IpcRendererEvent } from 'electron'
import { IPC } from '@shared/ipc-channels'
import type { Api, AudioApi, OverlayApi } from '@shared/api'
import type { AppState, OverlayTheme } from '@shared/types'

function subscribe<T>(channel: string, cb: (arg: T) => void): () => void {
  const handler = (_e: IpcRendererEvent, arg: T): void => cb(arg)
  ipcRenderer.on(channel, handler)
  return () => ipcRenderer.removeListener(channel, handler)
}

function subscribe0(channel: string, cb: () => void): () => void {
  const handler = (): void => cb()
  ipcRenderer.on(channel, handler)
  return () => ipcRenderer.removeListener(channel, handler)
}

const api: Api = {
  getConfig: () => ipcRenderer.invoke(IPC.CONFIG_GET),
  saveConfig: (data) => ipcRenderer.invoke(IPC.CONFIG_SAVE, data),
  getHistory: (offset, limit) => ipcRenderer.invoke(IPC.HISTORY_GET, offset, limit),
  clearHistory: () => ipcRenderer.invoke(IPC.HISTORY_CLEAR),
  runTest: (rawText, llmOverride) => ipcRenderer.invoke(IPC.PLAYGROUND_RUN, rawText, llmOverride),
  testSttConnection: (payload) => ipcRenderer.invoke(IPC.STT_TEST, payload),
  testLlmConnection: (payload) => ipcRenderer.invoke(IPC.LLM_TEST, payload),
  getVersion: () => ipcRenderer.invoke(IPC.APP_VERSION),
  getAllowedHotkeys: () => ipcRenderer.invoke(IPC.HOTKEY_ALLOWED),
  startHotkeyCapture: () => ipcRenderer.invoke(IPC.HOTKEY_CAPTURE_START),
  closeWindow: () => ipcRenderer.invoke(IPC.WINDOW_CLOSE),
  getGlossaryCandidates: (minCount) => ipcRenderer.invoke(IPC.CANDIDATES_GET, minCount),
  acceptGlossaryCandidate: (term) => ipcRenderer.invoke(IPC.CANDIDATES_ACCEPT, term),
  dismissGlossaryCandidate: (term) => ipcRenderer.invoke(IPC.CANDIDATES_DISMISS, term),
  onStateChanged: (cb) => subscribe(IPC.STATE_CHANGED, cb),
  onErrorOccurred: (cb) => subscribe(IPC.ERROR_OCCURRED, cb),
  onHotkeyCaptured: (cb) => subscribe(IPC.HOTKEY_CAPTURED, cb),
  onResultReady: (cb) => subscribe(IPC.RESULT_READY, cb),
}

const audioApi: AudioApi = {
  getOrtAssets: () => ipcRenderer.invoke(IPC.AUDIO_ORT_ASSETS),
  getVadModel: () => ipcRenderer.invoke(IPC.AUDIO_MODEL),
  onStart: (cb) => subscribe0(IPC.AUDIO_START, cb),
  onStop: (cb) => subscribe0(IPC.AUDIO_STOP, cb),
  sendSegment: (wav) => ipcRenderer.send(IPC.AUDIO_SEGMENT, wav),
  sendEnd: () => ipcRenderer.send(IPC.AUDIO_END),
  sendError: (message) => ipcRenderer.send(IPC.AUDIO_ERROR, message),
  sendLevel: (level) => ipcRenderer.send(IPC.AUDIO_LEVEL, level),
}

const overlayApi: OverlayApi = {
  onState: (cb) => subscribe<AppState>(IPC.OVERLAY_STATE, cb),
  onLevel: (cb) => subscribe<number>(IPC.OVERLAY_LEVEL, cb),
  onTheme: (cb) => subscribe<OverlayTheme>(IPC.OVERLAY_THEME, cb),
}

// 按窗口最小权限分流：主进程通过 additionalArguments 注入 --mt-role。
// 浮窗（纯展示）只拿只读的 overlayApi，拿不到配置读写(api) 或音频管线注入(audioApi)。
const roleArg = process.argv.find((a) => a.startsWith('--mt-role='))
const role = roleArg ? roleArg.slice('--mt-role='.length) : 'settings'
if (role === 'overlay') {
  contextBridge.exposeInMainWorld('overlayApi', overlayApi)
} else if (role === 'audio') {
  contextBridge.exposeInMainWorld('audioApi', audioApi)
} else {
  contextBridge.exposeInMainWorld('api', api)
}

export type PreloadApi = typeof api
