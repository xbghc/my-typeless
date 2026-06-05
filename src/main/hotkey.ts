// 全局热键监听 - 基于 uiohook-napi（keydown/keyup）。对应旧版 hotkey.py。
// 注意：uiohook 基于 SetWindowsHookEx 监听，无法“吞键”（return 1），故不抑制按键传播。
// 默认热键 right alt 单按不会激活系统菜单栏，影响可忽略（详见计划风险1）。
import { uIOhook, UiohookKey } from 'uiohook-napi'

// uiohook keycode → 配置键名。值取 UiohookKey 常量，区分左右修饰键（与旧版 VK 区分一致）。
const SPECIFIC: Record<number, string> = {
  [UiohookKey.Alt]: 'left alt',
  [UiohookKey.AltRight]: 'right alt',
  [UiohookKey.Ctrl]: 'left ctrl',
  [UiohookKey.CtrlRight]: 'right ctrl',
  [UiohookKey.Shift]: 'left shift',
  [UiohookKey.ShiftRight]: 'right shift',
  [UiohookKey.Meta]: 'left windows',
  [UiohookKey.MetaRight]: 'right windows',
  [UiohookKey.CapsLock]: 'caps lock',
  [UiohookKey.Tab]: 'tab',
  [UiohookKey.Space]: 'space',
  [UiohookKey.F1]: 'f1',
  [UiohookKey.F2]: 'f2',
  [UiohookKey.F3]: 'f3',
  [UiohookKey.F4]: 'f4',
  [UiohookKey.F5]: 'f5',
  [UiohookKey.F6]: 'f6',
  [UiohookKey.F7]: 'f7',
  [UiohookKey.F8]: 'f8',
  [UiohookKey.F9]: 'f9',
  [UiohookKey.F10]: 'f10',
  [UiohookKey.F11]: 'f11',
  [UiohookKey.F12]: 'f12',
}

// 通用键名（用户配 'alt' 时左右 alt 都匹配，比旧版更友好）。
const GENERIC: Record<string, string> = {
  'left alt': 'alt',
  'right alt': 'alt',
  'left ctrl': 'ctrl',
  'right ctrl': 'ctrl',
  'left shift': 'shift',
  'right shift': 'shift',
}

const noop = (): void => {}

interface UiohookEvent {
  keycode: number
}

export class HotkeyListener {
  private hotkey: string
  private pressed = false
  private started = false
  private capturing = false

  onPressed: () => void = noop
  onReleased: () => void = noop
  onCaptured: (key: string | null) => void = noop

  constructor(hotkey: string) {
    this.hotkey = hotkey.toLowerCase()
  }

  start(): void {
    if (this.started) return
    uIOhook.on('keydown', this.handleDown)
    uIOhook.on('keyup', this.handleUp)
    uIOhook.start()
    this.started = true
  }

  stop(): void {
    if (!this.started) return
    try {
      uIOhook.stop()
    } catch {
      // ignore
    }
    uIOhook.removeAllListeners()
    this.started = false
    this.pressed = false
  }

  updateHotkey(hotkey: string): void {
    this.hotkey = hotkey.toLowerCase()
    this.pressed = false
  }

  startCapture(): void {
    this.capturing = true
  }

  private matches(keycode: number): boolean {
    const name = SPECIFIC[keycode]
    if (!name) return false
    return name === this.hotkey || GENERIC[name] === this.hotkey
  }

  private handleDown = (e: UiohookEvent): void => {
    if (this.capturing) {
      if (e.keycode === UiohookKey.Escape) {
        this.capturing = false
        this.onCaptured(null)
        return
      }
      const name = SPECIFIC[e.keycode]
      if (name) {
        this.capturing = false
        this.onCaptured(name)
      }
      return
    }
    if (this.matches(e.keycode) && !this.pressed) {
      this.pressed = true
      this.onPressed()
    }
  }

  private handleUp = (e: UiohookEvent): void => {
    if (this.capturing) return
    if (this.matches(e.keycode) && this.pressed) {
      this.pressed = false
      this.onReleased()
    }
  }
}
