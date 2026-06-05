import { app } from 'electron'

/**
 * 运行时单实例：用 Electron 内置 lock 替代旧版 Win32 Named Mutex + Named Pipe。
 * 第二实例无法取得 lock，触发首实例的 second-instance 回调（打开设置窗口）后退出。
 *
 * 注意：安装器(NSIS)检测运行实例所需的同名 Win32 Mutex `MyTypeless_SingleInstance`
 * 在 M5 另行创建，与此 lock 互不冲突。
 */
export function ensureSingleInstance(onSecondInstance: () => void): boolean {
  const gotLock = app.requestSingleInstanceLock()
  if (!gotLock) {
    app.quit()
    return false
  }
  app.on('second-instance', () => onSecondInstance())
  return true
}
