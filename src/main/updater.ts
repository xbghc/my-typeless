// 自动更新 - electron-updater（GitHub Releases）。对应旧版 updater.py。
import { autoUpdater } from 'electron-updater'
import log from 'electron-log/main'

const CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000 // 4 小时

export interface UpdaterDeps {
  isDevMode: () => boolean
  onUpdateAvailable?: (version: string) => void
  onUpdateDownloaded?: (version: string) => void
}

export class Updater {
  private timer: ReturnType<typeof setInterval> | null = null

  constructor(private deps: UpdaterDeps) {
    autoUpdater.logger = log
    autoUpdater.autoDownload = true
    autoUpdater.autoInstallOnAppQuit = false
    autoUpdater.on('update-available', (info) => deps.onUpdateAvailable?.(info.version))
    autoUpdater.on('update-downloaded', (info) => deps.onUpdateDownloaded?.(info.version))
    autoUpdater.on('error', (err) =>
      log.error('Updater error: %s', err instanceof Error ? err.message : String(err)),
    )
  }

  start(): void {
    if (this.deps.isDevMode()) {
      log.info('Dev mode: skipping update check')
      return
    }
    void this.check()
    this.timer = setInterval(() => void this.check(), CHECK_INTERVAL_MS)
  }

  private async check(): Promise<void> {
    try {
      await autoUpdater.checkForUpdates()
    } catch (e) {
      log.error('checkForUpdates failed: %s', e instanceof Error ? e.message : String(e))
    }
  }

  quitAndInstall(): void {
    autoUpdater.quitAndInstall()
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
  }
}
