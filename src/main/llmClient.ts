// LLM 文本精修客户端 - 支持 OpenAI 兼容 API 与 Anthropic API。对应旧版 llm_client.py。
import OpenAI from 'openai'
import Anthropic from '@anthropic-ai/sdk'
import type { LLMConfig } from '@shared/types'
import { activeProvider, resolveSecret } from './config'

// 剥离推理模型内联的思维链 <think>…</think>（如 MiniMax-M2/M3），只保留最终书面文本。
const RE_THINK = /<think>[\s\S]*?<\/think>/gi
export function stripReasoning(text: string): string {
  return text
    .replace(RE_THINK, '') // 成对 <think>…</think>
    .replace(/<think>[\s\S]*$/i, '') // 被 max_tokens 截断的未闭合 <think>：删到结尾，别把思维链当结果注入
    .replace(/<\/think>/gi, '') // 残留的孤立 </think>（罕见嵌套）
    .trim()
}

export class LLMClient {
  private providerType: 'openai' | 'anthropic'
  private client: OpenAI | Anthropic
  private model: string
  private basePrompt: string

  constructor(config: LLMConfig) {
    const p = activeProvider(config)
    this.providerType = p?.provider_type ?? 'openai'
    this.model = config.active_model
    this.basePrompt = config.prompt
    const baseURL = p?.base_url ?? ''
    const apiKey = resolveSecret(p?.api_key ?? '')
    if (this.providerType === 'anthropic') {
      this.client = new Anthropic({ apiKey, baseURL: baseURL || undefined })
    } else {
      this.client = new OpenAI({ baseURL, apiKey })
    }
  }

  async refine(rawText: string, systemPrompt = '', context = ''): Promise<string> {
    const prompt = systemPrompt || this.basePrompt
    const userMessage = context
      ? `前文（仅供参考上下文，请勿重复输出）：\n${context}\n\n请精修以下新内容：\n${rawText}`
      : rawText

    if (this.providerType === 'anthropic') {
      const client = this.client as Anthropic
      const res = await client.messages.create({
        model: this.model,
        system: prompt,
        messages: [{ role: 'user', content: userMessage }],
        max_tokens: 4096,
      })
      const first = res.content[0]
      // 先 strip 再回退：think-only 响应 strip 后为空时回退到原始转写，绝不注入空串丢字。
      return stripReasoning(first && first.type === 'text' ? first.text : '') || rawText
    }

    const client = this.client as OpenAI
    const res = await client.chat.completions.create({
      model: this.model,
      messages: [
        { role: 'system', content: prompt },
        { role: 'user', content: userMessage },
      ],
    })
    return stripReasoning(res.choices[0]?.message?.content ?? '') || rawText
  }
}
