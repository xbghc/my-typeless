// 语音转文字客户端 - OpenAI 兼容 Whisper API。对应旧版 stt_client.py。
import OpenAI, { toFile } from 'openai'
import type { STTConfig } from '@shared/types'
import { activeProvider, resolveSecret } from './config'

export class STTClient {
  private client: OpenAI
  private model: string
  private language: string

  constructor(config: STTConfig) {
    const p = activeProvider(config)
    this.client = new OpenAI({ baseURL: p?.base_url ?? '', apiKey: resolveSecret(p?.api_key ?? '') })
    this.model = config.active_model
    this.language = config.language
  }

  async transcribe(audio: Buffer, prompt = ''): Promise<string> {
    const file = await toFile(audio, 'recording.wav')
    const res = await this.client.audio.transcriptions.create({
      model: this.model,
      file,
      ...(prompt ? { prompt } : {}),
      ...(this.language ? { language: this.language } : {}),
    })
    return res.text
  }
}
