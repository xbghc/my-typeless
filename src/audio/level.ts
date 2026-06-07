// 录音音量电平：纯计算，便于 node 环境单测（audio.ts 本体有 getUserMedia/ort 等浏览器副作用，不可直接测）。

/** 单帧 RMS（0..1）。样本为 Int16，归一化到 [-1,1] 后求均方根。 */
export function computeRms(frame: Int16Array): number {
  if (frame.length === 0) return 0
  let sum = 0
  for (let i = 0; i < frame.length; i++) {
    const s = frame[i] / 32768
    sum += s * s
  }
  return Math.sqrt(sum / frame.length)
}
