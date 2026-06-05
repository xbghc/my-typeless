// LLM 文本精修客户端 - 支持 OpenAI 兼容 API 与 Anthropic API。对应旧版 llm_client.py。
import OpenAI from 'openai'
import Anthropic from '@anthropic-ai/sdk'
import type { LLMConfig } from '@shared/types'
import { activeProvider } from './config'

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
    const apiKey = p?.api_key ?? ''
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
      return (first && first.type === 'text' ? first.text : null) || rawText
    }

    const client = this.client as OpenAI
    const res = await client.chat.completions.create({
      model: this.model,
      messages: [
        { role: 'system', content: prompt },
        { role: 'user', content: userMessage },
      ],
    })
    return res.choices[0]?.message?.content || rawText
  }
}
