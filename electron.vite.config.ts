import { resolve } from 'node:path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'

// 三个 renderer：设置窗口(src/renderer，React)、隐藏音频 worker(src/audio)、反馈浮窗(src/overlay)，后两者纯 TS。
// renderer.root 设为 src，使各 HTML 入口共享同一构建根；
// 产物落在 out/renderer/{renderer,audio,overlay}/index.html。
export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: { index: resolve(__dirname, 'src/main/index.ts') },
      },
    },
    resolve: {
      alias: { '@shared': resolve(__dirname, 'src/shared') },
    },
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: { index: resolve(__dirname, 'src/preload/index.ts') },
      },
    },
    resolve: {
      alias: { '@shared': resolve(__dirname, 'src/shared') },
    },
  },
  renderer: {
    root: resolve(__dirname, 'src'),
    build: {
      rollupOptions: {
        input: {
          settings: resolve(__dirname, 'src/renderer/index.html'),
          audio: resolve(__dirname, 'src/audio/index.html'),
          overlay: resolve(__dirname, 'src/overlay/index.html'),
        },
      },
    },
    plugins: [react()],
    resolve: {
      alias: {
        '@renderer': resolve(__dirname, 'src/renderer'),
        '@shared': resolve(__dirname, 'src/shared'),
      },
    },
  },
})
