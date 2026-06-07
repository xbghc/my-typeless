import { describe, expect, it } from 'vitest'
import { BAR_MIN, levelToBarHeight, nextOverlayView, pushBar } from '../src/overlay/view'
import { computeRms } from '../src/audio/level'

describe('overlay view-model', () => {
  it('maps state to css-state + label', () => {
    expect(nextOverlayView('recording')).toEqual({ cssState: 'recording', label: '聆听中…' })
    expect(nextOverlayView('processing')).toEqual({ cssState: 'processing', label: '处理中…' })
    expect(nextOverlayView('idle')).toEqual({ cssState: 'idle', label: '' })
  })

  it('levelToBarHeight clamps and keeps a minimum visible height', () => {
    expect(levelToBarHeight(0)).toBeCloseTo(BAR_MIN)
    expect(levelToBarHeight(1)).toBeCloseTo(1)
    expect(levelToBarHeight(-5)).toBeCloseTo(BAR_MIN) // 负数 clamp 到 0
    expect(levelToBarHeight(5)).toBeCloseTo(1) // >1 clamp 到 1
    const mid = levelToBarHeight(0.25)
    expect(mid).toBeGreaterThan(BAR_MIN)
    expect(mid).toBeLessThan(1)
  })

  it('pushBar scrolls and keeps a fixed length', () => {
    expect(pushBar([1, 2, 3], 4, 3)).toEqual([2, 3, 4])
    expect(pushBar([1, 2], 3, 3)).toEqual([1, 2, 3])
    expect(pushBar([], 1, 3)).toEqual([1])
  })
})

describe('audio level RMS', () => {
  it('is 0 for silence and empty input', () => {
    expect(computeRms(new Int16Array(0))).toBe(0)
    expect(computeRms(Int16Array.from([0, 0, 0, 0]))).toBe(0)
  })

  it('approaches 1 for full-scale and stays in 0..1', () => {
    const full = Int16Array.from([32767, -32768, 32767, -32768])
    const r = computeRms(full)
    expect(r).toBeGreaterThan(0.99)
    expect(r).toBeLessThanOrEqual(1)
  })

  it('half-amplitude square wave is about 0.5 RMS', () => {
    const half = Int16Array.from([16384, -16384, 16384, -16384])
    expect(computeRms(half)).toBeCloseTo(0.5, 2)
  })
})
