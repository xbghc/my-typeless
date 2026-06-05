import { app, dialog, Menu, nativeImage, Notification, Tray, type NativeImage } from 'electron'
import type { AppState } from '@shared/types'
import { resourcePath } from './resources'

// 加载失败时的纯色方块兜底。
function makeDot(r: number, g: number, b: number): NativeImage {
  const size = 16
  const buf = Buffer.alloc(size * size * 4)
  for (let i = 0; i < size * size; i++) {
    buf[i * 4] = b
    buf[i * 4 + 1] = g
    buf[i * 4 + 2] = r
    buf[i * 4 + 3] = 255
  }
  return nativeImage.createFromBitmap(buf, { width: size, height: size })
}

const FALLBACK: Record<AppState, NativeImage> = {
  idle: makeDot(0x9c, 0xa3, 0xaf),
  recording: makeDot(0xef, 0x44, 0x44),
  processing: makeDot(0xf5, 0x9e, 0x0b),
}

const ICON_FILE: Record<AppState, string> = {
  idle: 'icon_idle.png',
  recording: 'icon_recording.png',
  processing: 'icon_processing.png',
}

const TOOLTIP: Record<AppState, string> = {
  idle: 'My Typeless - Ready',
  recording: 'My Typeless - Recording...',
  processing: 'My Typeless - Processing...',
}

export class TrayManager {
  private tray: Tray | null = null
  private icons: Record<AppState, NativeImage> = FALLBACK
  onOpen: () => void = () => {}
  onQuit: () => void = () => {}

  private loadIcons(): void {
    const next = {} as Record<AppState, NativeImage>
    for (const state of ['idle', 'recording', 'processing'] as AppState[]) {
      const img = nativeImage.createFromPath(resourcePath(`icons/${ICON_FILE[state]}`))
      next[state] = img.isEmpty() ? FALLBACK[state] : img
    }
    this.icons = next
  }

  start(): void {
    this.loadIcons()
    this.tray = new Tray(this.icons.idle)
    this.tray.setToolTip(TOOLTIP.idle)
    this.tray.setContextMenu(
      Menu.buildFromTemplate([
        { label: 'Open', click: () => this.onOpen() },
        { type: 'separator' },
        { label: `About (v${app.getVersion()})`, click: () => this.showAbout() },
        { type: 'separator' },
        { label: 'Quit', click: () => this.onQuit() },
      ]),
    )
    this.tray.on('click', () => this.onOpen())
  }

  setState(state: AppState): void {
    if (!this.tray) return
    this.tray.setImage(this.icons[state])
    this.tray.setToolTip(TOOLTIP[state])
  }

  showAbout(): void {
    void dialog.showMessageBox({
      type: 'info',
      title: 'My Typeless',
      message: 'My Typeless',
      detail: `AI 语音听写工具\n版本 v${app.getVersion()}\n\nhttps://github.com/xbghc/my-typeless`,
      buttons: ['OK'],
    })
  }

  showNotification(title: string, body: string): void {
    if (Notification.isSupported()) new Notification({ title, body }).show()
  }

  showError(message: string, critical: boolean): void {
    this.showNotification(critical ? 'My Typeless - 错误' : 'My Typeless - 提示', message)
  }

  stop(): void {
    this.tray?.destroy()
    this.tray = null
  }
}
