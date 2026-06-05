/// <reference types="vite/client" />
import type { AudioApi } from '@shared/api'

// 纯 wasm 入口（避免打包 webgpu/jsep），复用主入口类型。
declare module 'onnxruntime-web/wasm' {
  export * from 'onnxruntime-web'
}

declare global {
  interface Window {
    audioApi: AudioApi
  }
}

export {}
