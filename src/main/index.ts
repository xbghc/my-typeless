import { app, BrowserWindow, ipcMain, session } from 'electron'
import { join } from 'node:path'
import { mkdirSync, readFileSync } from 'node:fs'
import { CONFIG_DIR, HISTORY_DB, HISTORY_JSON } from './paths'
import { initLogger } from './logger'
import { ensureSingleInstance } from './singleInstance'
import { TrayManager } from './tray'
import { loadConfig, isDevMode } from './config'
import { createDatabase, type DB } from './db'
import { HistoryStore } from './history'
import { CandidateStore } from './candidates'
import { registerIpc } from './ipc'
import { HotkeyListener } from './hotkey'
import { Worker } from './worker'
import { RecordingCoordinator } from './recordingCoordinator'
import { injectText } from './textInjector'
import { resourcePath } from './resources'
import { cleanupLegacyAutostart, setAutostart } from './autostart'
import { Updater } from './updater'
import { IPC } from '@shared/ipc-channels'
import type { AppConfig } from '@shared/types'

mkdirSync(CONFIG_DIR, { recursive: true })
const log = initLogger()

let settingsWin: BrowserWindow | null = null
let audioWin: BrowserWindow | null = null
let tray: TrayManager | null = null
let hotkey: HotkeyListener | null = null
let updater: Updater | null = null
let db: DB | null = null
let quitting = false
let coordinator: RecordingCoordinator | null = null

// 生产构建默认非 dev（不覆盖用户 prompt、启用更新检查）；开发运行默认 dev。
if (app.isPackaged && process.env.MY_TYPELESS_DEV === undefined) {
  process.env.MY_TYPELESS_DEV = '0'
}

let currentConfig: AppConfig = loadConfig()

const PRELOAD = join(__dirname, '../preload/index.js')
const RENDERER_DIR = join(__dirname, '../renderer')

function loadRenderer(win: BrowserWindow, entry: 'renderer' | 'audio'): void {
  const devUrl = process.env['ELECTRON_RENDERER_URL']
  if (devUrl) {
    void win.loadURL(`${devUrl}/${entry}/index.html`)
  } else {
    void win.loadFile(join(RENDERER_DIR, entry, 'index.html'))
  }
}

function createSettingsWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 820,
    height: 540,
    resizable: false,
    show: false,
    title: 'My Typeless',
    autoHideMenuBar: true,
    webPreferences: { preload: PRELOAD, sandbox: false, contextIsolation: true },
  })
  win.on('close', (e) => {
    if (!quitting) {
      e.preventDefault()
      win.hide()
    }
  })
  loadRenderer(win, 'renderer')
  return win
}

function createAudioWindow(): BrowserWindow {
  const win = new BrowserWindow({
    show: false,
    webPreferences: {
      preload: PRELOAD,
      sandbox: false,
      contextIsolation: true,
      backgroundThrottling: false,
    },
  })
  // 把音频 worker renderer 的 console 转发到主日志，便于诊断 VAD/录音。
  win.webContents.on('console-message', (_e, _level, message) => {
    log.info('[audio] %s', message)
  })
  loadRenderer(win, 'audio')
  return win
}

function openSettings(): void {
  if (!settingsWin || settingsWin.isDestroyed()) settingsWin = createSettingsWindow()
  settingsWin.show()
  settingsWin.focus()
}

function sendToSettings(channel: string, payload?: unknown): void {
  if (settingsWin && !settingsWin.isDestroyed()) settingsWin.webContents.send(channel, payload)
}

function quit(): void {
  quitting = true
  coordinator?.dispose()
  hotkey?.stop()
  updater?.stop()
  tray?.stop()
  db?.close()
  app.quit()
}

app.setAppUserModelId('xbghc.mytypeless.app.1')

if (ensureSingleInstance(() => openSettings())) {
  app.whenReady().then(() => {
    db = createDatabase(HISTORY_DB)
    const history = new HistoryStore(db, { legacyJsonPath: HISTORY_JSON })
    const candidates = new CandidateStore(db)

    // 仅放行麦克风（隐藏 worker 窗口 getUserMedia 需要），其余权限一律拒绝。
    session.defaultSession.setPermissionRequestHandler((_wc, permission, cb) =>
      cb(permission === 'media'),
    )

    const worker = new Worker(currentConfig, {
      textInjector: injectText,
      historyAdder: (raw, refined, timing) => history.add(raw, refined, timing),
      candidatesRecorder: (refined, glossary) => candidates.recordFromRefined(refined, glossary),
      onStateChange: (state) => {
        tray?.setState(state)
        sendToSettings(IPC.STATE_CHANGED, state)
      },
      onResult: (text) => sendToSettings(IPC.RESULT_READY, text),
      onError: (message, critical) => {
        log.error('Pipeline error: %s', message)
        tray?.showError(message, critical)
        sendToSettings(IPC.ERROR_OCCURRED, { message, critical })
      },
    })

    coordinator = new RecordingCoordinator({
      worker,
      startAudio: () => audioWin?.webContents.send(IPC.AUDIO_START),
      stopAudio: () => audioWin?.webContents.send(IPC.AUDIO_STOP),
      reloadAudio: () => {
        if (audioWin && !audioWin.isDestroyed()) audioWin.reload()
      },
      notify: (message) => tray?.showNotification('My Typeless', message),
      showError: (message, critical) => tray?.showError(message, critical),
      log: { warn: (m) => log.warn(m), error: (m) => log.error(m) },
    })

    hotkey = new HotkeyListener(currentConfig.hotkey)
    hotkey.onPressed = () => coordinator?.onPressed()
    hotkey.onReleased = () => coordinator?.onReleased()
    hotkey.onCaptured = (key) => sendToSettings(IPC.HOTKEY_CAPTURED, key)
    hotkey.start()

    registerIpc({
      getConfig: () => currentConfig,
      setConfig: (c) => {
        currentConfig = c
      },
      history,
      candidates,
      onConfigSaved: (c) => {
        worker.updateConfig(c)
        hotkey?.updateHotkey(c.hotkey)
        setAutostart(c.start_with_windows)
      },
      hideSettings: () => settingsWin?.hide(),
      startHotkeyCapture: () => hotkey?.startCapture(),
    })

    // 音频 worker 相关 IPC
    ipcMain.handle(IPC.AUDIO_ORT_ASSETS, () => {
      const dir = resourcePath('ort-wasm')
      const wasm = readFileSync(join(dir, 'ort-wasm-simd-threaded.wasm'))
      const mjs = readFileSync(join(dir, 'ort-wasm-simd-threaded.mjs'))
      return {
        wasm: wasm.buffer.slice(wasm.byteOffset, wasm.byteOffset + wasm.byteLength),
        mjs: mjs.buffer.slice(mjs.byteOffset, mjs.byteOffset + mjs.byteLength),
      }
    })
    ipcMain.handle(IPC.AUDIO_MODEL, () => {
      const u8 = readFileSync(resourcePath('silero_vad.onnx'))
      return u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength)
    })
    ipcMain.on(IPC.AUDIO_SEGMENT, (_e, wav: ArrayBuffer) => worker.pushSegment(Buffer.from(wav)))
    ipcMain.on(IPC.AUDIO_END, () => coordinator?.onAudioEnd())
    ipcMain.on(IPC.AUDIO_ERROR, (_e, message: string) => coordinator?.onAudioError(message))

    settingsWin = createSettingsWindow()
    audioWin = createAudioWindow()

    // 音频 worker 渲染进程崩溃：收尾当前录音并重载隐藏窗口（重载会重新预加载 VAD）。
    audioWin.webContents.on('render-process-gone', (_e, details) =>
      coordinator?.onAudioWorkerGone(details.reason),
    )

    tray = new TrayManager()
    tray.onOpen = openSettings
    tray.onQuit = quit
    tray.start()

    // 清理旧版开机自启注册表项，并按当前配置设置。
    cleanupLegacyAutostart()
    setAutostart(currentConfig.start_with_windows)

    updater = new Updater({
      isDevMode,
      onUpdateAvailable: (v) =>
        tray?.showNotification('My Typeless 更新', `发现新版本 v${v}，正在后台下载…`),
      onUpdateDownloaded: (v) => {
        tray?.showNotification('My Typeless 更新', `v${v} 已下载，重启后安装`)
        quitting = true
        updater?.quitAndInstall()
      },
    })
    updater.start()

    log.info('App ready (version %s)', app.getVersion())
  })

  app.on('window-all-closed', () => {})
}
