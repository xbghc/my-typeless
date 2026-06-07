// 反馈浮窗的纯视图逻辑：无 DOM 依赖，供 vitest（node 环境）单测（overlay.ts 本体有 DOM 副作用不可直接测）。
import type { AppState } from '@shared/types'

export interface OverlayView {
  cssState: AppState
  label: string
}

/** 把录音状态映射成胶囊的 data-state 与文案。idle 时由主进程隐藏窗口。 */
export function nextOverlayView(state: AppState): OverlayView {
  if (state === 'recording') return { cssState: 'recording', label: '聆听中…' }
  if (state === 'processing') return { cssState: 'processing', label: '处理中…' }
  return { cssState: 'idle', label: '' }
}

// 波形条的最小可见高度与数量（0..1，scaleY）。
export const BAR_MIN = 0.08
export const BAR_COUNT = 18

/** 0..1 的 RMS 电平 → 0..1 波形条高度。getUserMedia 开了 AGC/降噪压缩动态范围，
 *  用 sqrt 提升低音量可见度，并保留最小高度避免完全塌平。 */
export function levelToBarHeight(level: number): number {
  const clamped = level < 0 ? 0 : level > 1 ? 1 : level
  return BAR_MIN + (1 - BAR_MIN) * Math.sqrt(clamped)
}

/** 竖条历史滚动：新值入尾，保持固定长度（滚动波形效果）。 */
export function pushBar(bars: number[], next: number, size: number): number[] {
  const out = [...bars, next]
  while (out.length > size) out.shift()
  return out
}
