// 反馈浮窗渲染入口：监听 main 下行的 状态/电平/主题，更新底部居中胶囊。
// 纯视图逻辑在 ./view（供 node 单测），此文件只做 DOM 接线。
import type { AppState, OverlayTheme } from '@shared/types'
import { BAR_COUNT, BAR_MIN, levelToBarHeight, nextOverlayView, pushBar } from './view'

function start(): void {
  const root = document.getElementById('capsule')
  if (!root) return
  const label = root.querySelector<HTMLElement>('.label')
  const wave = root.querySelector<HTMLElement>('.wave')

  const barEls: HTMLElement[] = []
  if (wave) {
    for (let i = 0; i < BAR_COUNT; i++) {
      const b = document.createElement('span')
      b.className = 'bar'
      wave.appendChild(b)
      barEls.push(b)
    }
  }
  let bars = new Array<number>(BAR_COUNT).fill(BAR_MIN)

  const render = (): void => {
    for (let i = 0; i < barEls.length; i++) {
      barEls[i].style.transform = `scaleY(${bars[i]})`
    }
  }

  const applyState = (state: AppState): void => {
    const view = nextOverlayView(state)
    root.dataset.state = view.cssState
    if (label) label.textContent = view.label
    // 离开录音态：波形归零。
    if (state !== 'recording') {
      bars = new Array<number>(BAR_COUNT).fill(BAR_MIN)
      render()
    }
  }

  const applyTheme = (theme: OverlayTheme): void => {
    if (theme === 'auto') delete root.dataset.theme
    else root.dataset.theme = theme
  }

  window.overlayApi.onState(applyState)
  window.overlayApi.onLevel((level) => {
    if (root.dataset.state !== 'recording') return
    bars = pushBar(bars, levelToBarHeight(level), BAR_COUNT)
    render()
  })
  window.overlayApi.onTheme(applyTheme)
  render()
}

start()
