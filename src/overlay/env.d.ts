/// <reference types="vite/client" />
import type { OverlayApi } from '@shared/api'

declare global {
  interface Window {
    overlayApi: OverlayApi
  }
}

export {}
