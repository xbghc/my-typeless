// 把 onnxruntime-web 的 wasm/mjs 复制到 resources/ort-wasm/。
// 运行时由 main 读取并经 IPC 以 blob URL 提供给 audio worker（绕开 Vite asset / 跨协议问题）。
import { copyFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const src = join(root, 'node_modules', 'onnxruntime-web', 'dist')
const dst = join(root, 'resources', 'ort-wasm')
mkdirSync(dst, { recursive: true })

const files = ['ort-wasm-simd-threaded.wasm', 'ort-wasm-simd-threaded.mjs']
for (const f of files) {
  copyFileSync(join(src, f), join(dst, f))
}
console.log(`Copied ${files.length} ort wasm asset(s) to resources/ort-wasm/`)
