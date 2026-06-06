// 录音协调器：把热键 / 音频 IPC 事件编排成对 worker 的调用，集中处理重入忽略、
// 录音超时兜底(watchdog)、音频 worker 崩溃收尾、麦克风失败提示。
// 从 main/index.ts 抽出以便单测——依赖全部注入，不耦合 Electron。

export interface CoordinatorWorker {
  isRunning(): boolean
  startRecording(): void
  stopRecording(): void
  finishSegments(): void
}

export interface CoordinatorDeps {
  worker: CoordinatorWorker
  startAudio(): void // 通知音频 worker 开始录音（IPC AUDIO_START）
  stopAudio(): void // 通知音频 worker 停止录音（IPC AUDIO_STOP）
  reloadAudio(): void // 重载隐藏音频窗口（崩溃恢复）
  notify(message: string): void // 托盘提示（重入忽略时告知用户）
  showError(message: string, critical: boolean): void
  log: { warn(message: string): void; error(message: string): void }
  watchdogMs?: number // AUDIO_END 兜底超时，默认 5000ms
}

export class RecordingCoordinator {
  private pressIgnored = false
  private watchdog: ReturnType<typeof setTimeout> | null = null
  private readonly watchdogMs: number

  constructor(private deps: CoordinatorDeps) {
    this.watchdogMs = deps.watchdogMs ?? 5000
  }

  // 热键按下：上一段仍在处理时忽略本次触发，避免注入串位、状态被旧流程覆盖。
  onPressed(): void {
    if (this.deps.worker.isRunning()) {
      this.pressIgnored = true
      this.deps.notify('正在处理上一段，请稍候…')
      return
    }
    this.pressIgnored = false
    this.deps.worker.startRecording()
    this.deps.startAudio()
  }

  // 热键松开：忽略与“被忽略的按下”配对的松开；否则停止录音并装载兜底 watchdog。
  onReleased(): void {
    if (this.pressIgnored) {
      this.pressIgnored = false
      return
    }
    this.deps.worker.stopRecording()
    this.deps.stopAudio()
    this.clearWatchdog()
    // 音频窗口若未发回 AUDIO_END（崩溃 / getUserMedia 失败），到时强制收尾，避免卡在 processing。
    if (this.deps.worker.isRunning()) {
      this.watchdog = setTimeout(() => {
        this.watchdog = null
        this.deps.log.warn('AUDIO_END 超时未达，强制结束分段流')
        this.deps.worker.finishSegments()
      }, this.watchdogMs)
    }
  }

  // 收到段流结束：取消 watchdog，正常收尾。
  onAudioEnd(): void {
    this.clearWatchdog()
    this.deps.worker.finishSegments()
  }

  // 音频 worker 报错（多为麦克风不可用）：录音中则收尾并提示。
  onAudioError(message: string): void {
    this.deps.log.error(`Audio error: ${message}`)
    if (this.deps.worker.isRunning()) {
      this.clearWatchdog()
      this.deps.worker.finishSegments()
      this.deps.showError('麦克风不可用或录音失败，请检查麦克风权限与设备。', true)
    }
  }

  // 音频 worker 渲染进程退出：录音中则收尾，并重载隐藏窗口（重载会重新预加载 VAD）。
  onAudioWorkerGone(reason: string): void {
    this.deps.log.error(`Audio worker 渲染进程退出(${reason})，重载隐藏窗口`)
    this.clearWatchdog()
    if (this.deps.worker.isRunning()) this.deps.worker.finishSegments()
    this.deps.reloadAudio()
  }

  dispose(): void {
    this.clearWatchdog()
  }

  private clearWatchdog(): void {
    if (this.watchdog) {
      clearTimeout(this.watchdog)
      this.watchdog = null
    }
  }
}
