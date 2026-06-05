// 把 STT/LLM 处理过程中的异常映射为 (用户可读中文消息, 是否严重)。
// 逐字对应旧版 worker.py 的 _map_processing_error，同时覆盖 openai 与 anthropic 两套 SDK 的 error 类。
import OpenAI from 'openai'
import Anthropic from '@anthropic-ai/sdk'
import type { ErrorPayload } from '@shared/types'

// 两套 SDK 的 error 类同名但是不同的类，需都判断。
const SDKS = [OpenAI, Anthropic] as const

function isInstance(e: unknown, ctor: unknown): boolean {
  return typeof ctor === 'function' && e instanceof (ctor as new (...args: never[]) => object)
}

export function mapProcessingError(e: unknown): ErrorPayload {
  const msg = e instanceof Error ? e.message : String(e)

  for (const SDK of SDKS) {
    if (isInstance(e, SDK.AuthenticationError)) {
      return { message: 'API 密钥无效或已过期，请在设置中检查 API Key 是否正确。', critical: true }
    }
    // 超时是连接错误的子类，必须先于连接错误判断。
    if (isInstance(e, SDK.APIConnectionTimeoutError)) {
      return { message: 'API 请求超时，请检查网络连接或稍后重试。', critical: false }
    }
    if (isInstance(e, SDK.APIConnectionError)) {
      return { message: '无法连接到 API 服务器，请检查网络连接和 API 地址是否正确。', critical: true }
    }
    if (isInstance(e, SDK.NotFoundError)) {
      return { message: 'API 模型或接口未找到，请检查模型名称和 API 地址是否正确。', critical: true }
    }
    if (isInstance(e, SDK.BadRequestError)) {
      return { message: `API 请求参数错误：${msg}`, critical: true }
    }
    if (isInstance(e, SDK.RateLimitError)) {
      return { message: 'API 请求过于频繁，请稍后再试或检查额度是否充足。', critical: false }
    }
    if (isInstance(e, SDK.APIError)) {
      const status = (e as { status?: number }).status
      const s = status != null ? `HTTP ${status}` : 'HTTP 状态未知'
      return { message: `API 服务异常 (${s})，请稍后重试。`, critical: false }
    }
  }

  return { message: `发生未知错误：${msg}`, critical: false }
}
