// 让 main 进程的 node HTTP（openai / @anthropic-ai/sdk 的 fetch）走系统代理。
// 国内访问海外 API（如 Groq）时，node 默认不读系统代理、直连会被拦（403）；这里显式跟随。
import { setGlobalDispatcher, ProxyAgent } from 'undici'
import { session } from 'electron'

interface Logger {
  info: (msg: string, ...args: unknown[]) => void
}

/** 隐去代理 URL 内的 user:password，避免凭据写入磁盘日志；解析失败则按 //user@ 形式兜底打码。 */
function redactProxy(url: string): string {
  try {
    const u = new URL(url)
    return u.username || u.password ? `${u.protocol}//${u.host}` : url
  } catch {
    return url.replace(/\/\/[^/@]*@/, '//***@')
  }
}

/** 应用代理到全局 fetch dispatcher：优先环境变量，其次系统代理（Chromium 解析，Windows 读 WinINET）。 */
export async function applySystemProxy(log: Logger): Promise<void> {
  const envProxy =
    process.env.HTTPS_PROXY ||
    process.env.HTTP_PROXY ||
    process.env.https_proxy ||
    process.env.http_proxy
  if (envProxy) {
    try {
      setGlobalDispatcher(new ProxyAgent(envProxy))
      log.info('[proxy] env proxy: %s', redactProxy(envProxy))
      return
    } catch (e) {
      // 无 scheme（如 HTTPS_PROXY=127.0.0.1:7897）等非法值会让 ProxyAgent 抛错；
      // 必须吞掉并继续探测系统代理——否则未捕获的拒绝会中断整个 app 初始化、卡死单实例锁。
      log.info(
        '[proxy] invalid env proxy %s: %s',
        redactProxy(envProxy),
        e instanceof Error ? e.message : String(e),
      )
    }
  }
  try {
    // 用任意 https 目标探测系统代理；返回形如 "PROXY 127.0.0.1:7897" / "DIRECT" / "PROXY a;PROXY b"。
    const resolved = await session.defaultSession.resolveProxy('https://api.openai.com')
    const first = (resolved || 'DIRECT').split(';')[0].trim()
    if (first.toUpperCase().startsWith('PROXY ')) {
      const url = 'http://' + first.slice(6).trim()
      setGlobalDispatcher(new ProxyAgent(url))
      log.info('[proxy] system proxy: %s', url)
      return
    }
  } catch (e) {
    log.info('[proxy] resolveProxy failed: %s', e instanceof Error ? e.message : String(e))
  }
  log.info('[proxy] direct (no proxy)')
}
