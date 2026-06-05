import { app } from 'electron'
import { execFile } from 'node:child_process'

// 开机自启：用 Electron 内置 API 写 HKCU Run 值，替代旧 Inno Setup 注册表项。
export function setAutostart(enabled: boolean): void {
  app.setLoginItemSettings({ openAtLogin: enabled })
}

// 清理旧 Python 版写入的 HKCU Run\MyTypeless 值（指向已失效的旧 exe）。
export function cleanupLegacyAutostart(): void {
  execFile(
    'reg',
    ['delete', 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run', '/v', 'MyTypeless', '/f'],
    () => {
      // 值不存在时 reg 报错，忽略。
    },
  )
}
