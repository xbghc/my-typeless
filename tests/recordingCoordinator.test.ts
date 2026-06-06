import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RecordingCoordinator, type CoordinatorDeps } from '@main/recordingCoordinator'

// 构造可控的假依赖：worker.isRunning 由内部标志驱动，startRecording/finishSegments 翻转它。
function setup(running = false) {
  let r = running
  const worker = {
    isRunning: vi.fn(() => r),
    startRecording: vi.fn(() => {
      r = true
    }),
    stopRecording: vi.fn(),
    finishSegments: vi.fn(() => {
      r = false
    }),
  }
  const startAudio = vi.fn()
  const stopAudio = vi.fn()
  const reloadAudio = vi.fn()
  const notify = vi.fn()
  const showError = vi.fn()
  const logWarn = vi.fn()
  const logError = vi.fn()
  const deps: CoordinatorDeps = {
    worker,
    startAudio,
    stopAudio,
    reloadAudio,
    notify,
    showError,
    log: { warn: logWarn, error: logError },
    watchdogMs: 5000,
  }
  const coord = new RecordingCoordinator(deps)
  return { coord, worker, startAudio, stopAudio, reloadAudio, notify, showError, logWarn, logError }
}

describe('RecordingCoordinator', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('starts recording + audio on press when idle', () => {
    const t = setup(false)
    t.coord.onPressed()
    expect(t.worker.startRecording).toHaveBeenCalledTimes(1)
    expect(t.startAudio).toHaveBeenCalledTimes(1)
    expect(t.notify).not.toHaveBeenCalled()
  })

  it('ignores re-entrant press while processing and swallows the paired release', () => {
    const t = setup(true) // 上一段仍在处理
    t.coord.onPressed()
    expect(t.worker.startRecording).not.toHaveBeenCalled()
    expect(t.startAudio).not.toHaveBeenCalled()
    expect(t.notify).toHaveBeenCalledTimes(1)
    // 配对的松开必须被吞掉：不停止录音、不装 watchdog。
    t.coord.onReleased()
    expect(t.worker.stopRecording).not.toHaveBeenCalled()
    expect(t.stopAudio).not.toHaveBeenCalled()
  })

  it('stops recording + audio on release and arms the watchdog while running', () => {
    const t = setup(false)
    t.coord.onPressed() // running=true
    t.coord.onReleased()
    expect(t.worker.stopRecording).toHaveBeenCalledTimes(1)
    expect(t.stopAudio).toHaveBeenCalledTimes(1)
    // watchdog 到时强制收尾。
    vi.advanceTimersByTime(5000)
    expect(t.worker.finishSegments).toHaveBeenCalledTimes(1)
    expect(t.logWarn).toHaveBeenCalled()
  })

  it('AUDIO_END finishes segments and cancels the watchdog', () => {
    const t = setup(false)
    t.coord.onPressed()
    t.coord.onReleased()
    t.coord.onAudioEnd()
    expect(t.worker.finishSegments).toHaveBeenCalledTimes(1)
    // watchdog 不得再触发第二次收尾。
    vi.advanceTimersByTime(10000)
    expect(t.worker.finishSegments).toHaveBeenCalledTimes(1)
  })

  it('mic/audio error while running finishes segments and surfaces an error', () => {
    const t = setup(false)
    t.coord.onPressed() // running
    t.coord.onAudioError('getUserMedia failed')
    expect(t.worker.finishSegments).toHaveBeenCalledTimes(1)
    expect(t.showError).toHaveBeenCalledTimes(1)
    expect(t.logError).toHaveBeenCalled()
    // 已收尾(非 running)：随后的松开不应再装 watchdog。
    t.coord.onReleased()
    vi.advanceTimersByTime(10000)
    expect(t.worker.finishSegments).toHaveBeenCalledTimes(1)
  })

  it('audio error while idle is logged but does not touch the pipeline', () => {
    const t = setup(false) // 空闲（如预加载 VAD 失败）
    t.coord.onAudioError('preload VAD failed')
    expect(t.worker.finishSegments).not.toHaveBeenCalled()
    expect(t.showError).not.toHaveBeenCalled()
    expect(t.logError).toHaveBeenCalled()
  })

  it('audio worker gone while running finishes segments and reloads', () => {
    const t = setup(false)
    t.coord.onPressed() // running
    t.coord.onAudioWorkerGone('crashed')
    expect(t.worker.finishSegments).toHaveBeenCalledTimes(1)
    expect(t.reloadAudio).toHaveBeenCalledTimes(1)
  })

  it('audio worker gone while idle still reloads but does not finish', () => {
    const t = setup(false)
    t.coord.onAudioWorkerGone('crashed')
    expect(t.worker.finishSegments).not.toHaveBeenCalled()
    expect(t.reloadAudio).toHaveBeenCalledTimes(1)
  })

  it('dispose cancels a pending watchdog', () => {
    const t = setup(false)
    t.coord.onPressed()
    t.coord.onReleased()
    t.coord.dispose()
    vi.advanceTimersByTime(10000)
    expect(t.worker.finishSegments).not.toHaveBeenCalled()
  })
})
