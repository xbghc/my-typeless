// 文本注入：备份剪贴板 → 写入精修文本 → 模拟 Ctrl+V → 还原剪贴板。对应旧版 text_injector.py。
// Windows on ARM 上 nut.js 无预编译，改用 ffi-rs 直接调 user32!keybd_event（NAPI，跨架构）。
import { clipboard } from 'electron'
import { DataType, load, open } from 'ffi-rs'

const VK_CONTROL = 0x11
const VK_V = 0x56
const KEYEVENTF_KEYUP = 0x0002

let libOpened = false
function ensureUser32(): void {
  if (libOpened) return
  open({ library: 'user32', path: 'user32.dll' })
  libOpened = true
}

// void keybd_event(BYTE bVk, BYTE bScan, DWORD dwFlags, ULONG_PTR dwExtraInfo)
function keybdEvent(vk: number, flags: number): void {
  load({
    library: 'user32',
    funcName: 'keybd_event',
    retType: DataType.Void,
    paramsType: [DataType.U8, DataType.U8, DataType.I32, DataType.I64],
    paramsValue: [vk, 0, flags, 0],
  })
}

function sendCtrlV(): void {
  keybdEvent(VK_CONTROL, 0)
  keybdEvent(VK_V, 0)
  keybdEvent(VK_V, KEYEVENTF_KEYUP)
  keybdEvent(VK_CONTROL, KEYEVENTF_KEYUP)
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function injectText(text: string): Promise<void> {
  ensureUser32()
  const backup = clipboard.readText()
  clipboard.writeText(text)
  await delay(50)
  sendCtrlV()
  await delay(200)
  clipboard.writeText(backup)
}
