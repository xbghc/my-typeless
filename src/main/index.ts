import { app, BrowserWindow, ipcMain, screen, session } from 'electron'
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
import { applySystemProxy } from './proxy'
import { IPC } from '@shared/ipc-channels'
import type { AppConfig, AppState } from '@shared/types'

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
let overlayWin: BrowserWindow | null = null
let overlayHideTimer: ReturnType<typeof setTimeout> | null = null
let currentAppState: AppState = 'idle'

// 生产构建默认非 dev（不覆盖用户 prompt、启用更新检查）；开发运行默认 dev。
if (app.isPackaged && process.env.MY_TYPELESS_DEV === undefined) {
  process.env.MY_TYPELESS_DEV = '0'
}

let currentConfig: AppConfig = loadConfig()

const PRELOAD = join(__dirname, '../preload/index.js')
const RENDERER_DIR = join(__dirname, '../renderer')

function loadRenderer(win: BrowserWindow, entry: 'renderer' | 'audio' | 'overlay'): void {
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
      additionalArguments: ['--mt-role=audio'], // preload 据此只暴露 audioApi
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

// ── 反馈浮窗（src/overlay）：底部居中胶囊，录音/处理时浮出，不抢焦点、整窗鼠标穿透 ──
const OVERLAY_W = 240
const OVERLAY_H = 64

function createOverlayWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: OVERLAY_W,
    height: OVERLAY_H,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    hasShadow: false,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    focusable: false, // 绝不抢焦点，避免打断用户输入
    skipTaskbar: true,
    alwaysOnTop: true,
    webPreferences: {
      preload: PRELOAD,
      sandbox: false,
      contextIsolation: true,
      backgroundThrottling: false,
      additionalArguments: ['--mt-role=overlay'], // preload 据此只暴露只读 overlayApi（最小权限）
    },
  })
  // 靠 topmost + skipTaskbar 浮在普通窗口 / 任务栏之上。注意：Windows 上 level 形参几乎等价、
  // 不构成 z 序差异；能否被全屏遮挡取决于对方全屏方式——独占全屏(DX exclusive)会盖住本窗（符合预期），
  // 但 borderless 窗口化全屏（主流游戏/视频/浏览器全屏）仍会被本浮窗覆盖底部。
  win.setAlwaysOnTop(true, 'pop-up-menu')
  win.setIgnoreMouseEvents(true) // 整窗鼠标穿透，纯展示
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' })) // 纯展示窗，禁止打开任何新窗口
  // 窗口就绪后推一次当前主题，避免加载时序丢失。
  win.webContents.on('did-finish-load', () => {
    win.webContents.send(IPC.OVERLAY_THEME, currentConfig.overlay.theme)
    // 冷启动后、页面就绪前若已进入录音/处理态，先前的 OVERLAY_STATE 已被丢弃，这里补推最新态。
    if (currentAppState === 'recording' || currentAppState === 'processing') {
      win.webContents.send(IPC.OVERLAY_STATE, currentAppState)
    }
  })
  win.on('close', (e) => {
    if (!quitting) {
      e.preventDefault()
      win.hide()
    }
  })
  // 渲染进程崩溃恢复（对齐音频窗）：销毁并置空，showOverlay 会在下次需要时重建，避免永久空窗。
  win.webContents.on('render-process-gone', () => {
    if (quitting) return
    log.error('[overlay] renderer gone; will recreate on next show')
    if (overlayHideTimer) {
      clearTimeout(overlayHideTimer)
      overlayHideTimer = null
    }
    win.destroy()
    if (overlayWin === win) overlayWin = null
  })
  loadRenderer(win, 'overlay')
  return win
}

function positionOverlay(win: BrowserWindow): void {
  // 跟随用户当前活动屏：取光标所在显示器（热键触发时光标通常在输入处那块屏）。
  // workArea 是 DIP（与 setBounds 同坐标系），DPI 正确，绝不乘 scaleFactor。
  const { workArea } = screen.getDisplayNearestPoint(screen.getCursorScreenPoint())
  const x = Math.round(workArea.x + (workArea.width - OVERLAY_W) / 2)
  const y = Math.round(workArea.y + workArea.height - OVERLAY_H - 48)
  win.setBounds({ x, y, width: OVERLAY_W, height: OVERLAY_H })
}

function sendToOverlay(channel: string, payload?: unknown): void {
  if (overlayWin && !overlayWin.isDestroyed()) overlayWin.webContents.send(channel, payload)
}

function showOverlay(state: AppState): void {
  if (!currentConfig.overlay.enabled) return
  // 懒创建/崩溃恢复：窗口缺失或已销毁（含渲染进程崩溃后）时重建。
  if (!overlayWin || overlayWin.isDestroyed()) overlayWin = createOverlayWindow()
  if (overlayHideTimer) {
    clearTimeout(overlayHideTimer)
    overlayHideTimer = null
  }
  if (!overlayWin.isVisible()) {
    positionOverlay(overlayWin)
    overlayWin.showInactive() // 不抢焦点
  }
  sendToOverlay(IPC.OVERLAY_STATE, state)
}

function hideOverlay(): void {
  if (!overlayWin || overlayWin.isDestroyed()) return
  // 先发 idle 让渲染层淡出，延迟到动画结束后再真正隐藏窗口。
  sendToOverlay(IPC.OVERLAY_STATE, 'idle')
  if (overlayHideTimer) clearTimeout(overlayHideTimer)
  overlayHideTimer = setTimeout(() => {
    overlayHideTimer = null
    if (overlayWin && !overlayWin.isDestroyed()) overlayWin.hide()
  }, 220)
}

function quit(): void {
  quitting = true
  coordinator?.dispose()
  if (overlayHideTimer) clearTimeout(overlayHideTimer)
  overlayWin?.destroy()
  hotkey?.stop()
  updater?.stop()
  tray?.stop()
  db?.close()
  app.quit()
}

app.setAppUserModelId('xbghc.mytypeless.app.1')

if (ensureSingleInstance(() => openSettings())) {
  app.whenReady().then(async () => {
    // 让 openai / anthropic SDK 的 node fetch 跟随系统代理（国内访问海外 STT/LLM 必需）。
    // 代理设置绝不能中断初始化：任何失败都吞掉并直连，否则会卡死单实例锁、整个 app 无界面无热键。
    try {
      await applySystemProxy(log)
    } catch (e) {
      log.error('[proxy] setup failed, continuing direct: %s', e instanceof Error ? e.message : String(e))
    }
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
        currentAppState = state
        tray?.setState(state)
        sendToSettings(IPC.STATE_CHANGED, state)
        // 录音/处理时浮出反馈浮窗，回到 idle 时淡出隐藏。
        if (state === 'recording' || state === 'processing') showOverlay(state)
        else hideOverlay()
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
        // overlay 开关：启用则确保窗口存在（新窗口的 did-finish-load 会推主题）；禁用则销毁、释放渲染进程。
        if (c.overlay.enabled) {
          if (!overlayWin || overlayWin.isDestroyed()) overlayWin = createOverlayWindow()
          sendToOverlay(IPC.OVERLAY_THEME, c.overlay.theme)
          // 运行中开启：若此刻正录音/处理，onStateChange 不会再触发，需立即补显示本次会话。
          if (currentAppState === 'recording' || currentAppState === 'processing') {
            showOverlay(currentAppState)
          }
        } else {
          if (overlayHideTimer) {
            clearTimeout(overlayHideTimer)
            overlayHideTimer = null
          }
          overlayWin?.destroy()
          overlayWin = null
        }
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
    // 录音音量电平：仅录音态且浮窗可见时转发给 overlay 做波形，否则丢弃（避免无谓 IPC）。
    ipcMain.on(IPC.AUDIO_LEVEL, (_e, level: number) => {
      if (currentAppState === 'recording' && overlayWin?.isVisible()) {
        sendToOverlay(IPC.OVERLAY_LEVEL, level)
      }
    })

    settingsWin = createSettingsWindow()
    audioWin = createAudioWindow()
    // 仅在启用时创建浮窗（一个隐藏 renderer 进程）；关闭时不占资源，运行中开关在 onConfigSaved 补建。
    if (currentConfig.overlay.enabled) overlayWin = createOverlayWindow()

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
