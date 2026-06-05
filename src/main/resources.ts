import { app } from 'electron'
import { join } from 'node:path'

// 资源定位：dev 取项目 resources/，打包后取 process.resourcesPath（electron-builder extraResources）。
export function resourcePath(name: string): string {
  if (app.isPackaged) return join(process.resourcesPath, name)
  return join(app.getAppPath(), 'resources', name)
}
