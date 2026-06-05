// 在 node(测试) 与 electron(运行/打包) 之间切换 better-sqlite3 的预编译 ABI。
// better-sqlite3 是非 NAPI 原生模块，两种 runtime 的 ABI 不同，需切换。
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const runtime = process.argv[2] === 'electron' ? 'electron' : 'node'

const args = ['prebuild-install', '-r', runtime]
if (runtime === 'electron') {
  args.push('-t', require('electron/package.json').version)
}

execFileSync('npx', args, {
  cwd: join(root, 'node_modules', 'better-sqlite3'),
  stdio: 'inherit',
  shell: true,
})
console.log(`\nbetter-sqlite3 -> ${runtime} ABI`)
