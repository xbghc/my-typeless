// 配置加载/保存/迁移。逐字对应旧版 config.py（含 legacy→providers 迁移、DEV_MODE、两段 prompt 构造）。
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { CONFIG_FILE } from './paths'
import { DEFAULT_LLM_PROMPT } from '@shared/prompts'
import type { AppConfig, LLMConfig, ProviderConfig, STTConfig } from '@shared/types'

export { DEFAULT_LLM_PROMPT }

/** DEV_MODE：环境变量 MY_TYPELESS_DEV，默认 "1"(dev)。仅显式 "1" 为 dev。 */
export function isDevMode(): boolean {
  return (process.env.MY_TYPELESS_DEV ?? '1') === '1'
}

export function defaultSttConfig(): STTConfig {
  return {
    providers: [
      {
        id: 'default-stt',
        name: 'Groq',
        base_url: 'https://api.groq.com/openai/v1',
        api_key: '',
        models: ['whisper-large-v3'],
        provider_type: 'openai',
      },
    ],
    active_provider_id: 'default-stt',
    active_model: 'whisper-large-v3',
    // 默认中文：Whisper auto-detect 中文常输出繁体并偶发误判，显式 "zh" + zhconv 后处理是社区共识。
    language: 'zh',
  }
}

export function defaultLlmConfig(): LLMConfig {
  return {
    providers: [
      {
        id: 'default-llm',
        name: 'DeepSeek',
        base_url: 'https://api.deepseek.com/v1',
        api_key: '',
        models: ['deepseek-chat'],
        provider_type: 'openai',
      },
    ],
    active_provider_id: 'default-llm',
    active_model: 'deepseek-chat',
    prompt: DEFAULT_LLM_PROMPT,
  }
}

export function defaultConfig(): AppConfig {
  return {
    hotkey: 'right alt',
    start_with_windows: false,
    stt: defaultSttConfig(),
    llm: defaultLlmConfig(),
    glossary: [],
  }
}

export function activeProvider(
  cfg: { providers: ProviderConfig[]; active_provider_id: string },
): ProviderConfig | null {
  return (
    cfg.providers.find((p) => p.id === cfg.active_provider_id) ?? cfg.providers[0] ?? null
  )
}

interface RawObj {
  [key: string]: unknown
}

// 复刻 ProviderConfig(**p)：缺 id/name/base_url/api_key 视为坏数据（由 loadConfig 捕获回退默认）。
function toProvider(p: RawObj): ProviderConfig {
  if (p.id == null || p.name == null || p.base_url == null || p.api_key == null) {
    throw new Error('invalid provider entry')
  }
  return {
    id: String(p.id),
    name: String(p.name),
    base_url: String(p.base_url),
    api_key: String(p.api_key),
    models: Array.isArray(p.models) ? (p.models as unknown[]).map(String) : [],
    provider_type: p.provider_type === 'anthropic' ? 'anthropic' : 'openai',
  }
}

/** 把任意来源的配置对象规范化为 AppConfig，复刻 config.py.load 的迁移规则。 */
export function migrateConfig(data: RawObj, devMode: boolean): AppConfig {
  const sttData = (data.stt ?? {}) as RawObj
  let sttProviders: ProviderConfig[]
  if ('providers' in sttData) {
    sttProviders = (sttData.providers as RawObj[]).map(toProvider)
  } else if ('base_url' in sttData) {
    sttProviders = [
      {
        id: 'migrated-stt',
        name: 'Legacy STT',
        base_url: String(sttData.base_url ?? 'https://api.groq.com/openai/v1'),
        api_key: String(sttData.api_key ?? ''),
        models: [String(sttData.model ?? 'whisper-large-v3')],
        provider_type: 'openai',
      },
    ]
  } else {
    sttProviders = defaultSttConfig().providers
  }
  const sttLegacy = 'base_url' in sttData && !('providers' in sttData)
  const stt: STTConfig = {
    providers: sttProviders,
    active_provider_id: String(
      sttData.active_provider_id ?? (sttLegacy ? 'migrated-stt' : 'default-stt'),
    ),
    active_model: String(sttData.active_model ?? sttData.model ?? 'whisper-large-v3'),
    language: String(sttData.language ?? ''),
  }

  const llmData = (data.llm ?? {}) as RawObj
  let llmProviders: ProviderConfig[]
  if ('providers' in llmData) {
    llmProviders = (llmData.providers as RawObj[]).map(toProvider)
  } else if ('base_url' in llmData) {
    llmProviders = [
      {
        id: 'migrated-llm',
        name: 'Legacy LLM',
        base_url: String(llmData.base_url ?? 'https://api.deepseek.com/v1'),
        api_key: String(llmData.api_key ?? ''),
        models: [String(llmData.model ?? 'deepseek-chat')],
        provider_type: 'openai',
      },
    ]
  } else {
    llmProviders = defaultLlmConfig().providers
  }
  const llmLegacy = 'base_url' in llmData && !('providers' in llmData)
  const llm: LLMConfig = {
    providers: llmProviders,
    active_provider_id: String(
      llmData.active_provider_id ?? (llmLegacy ? 'migrated-llm' : 'default-llm'),
    ),
    active_model: String(llmData.active_model ?? llmData.model ?? 'deepseek-chat'),
    prompt: typeof llmData.prompt === 'string' ? llmData.prompt : DEFAULT_LLM_PROMPT,
  }

  const glossary = Array.isArray(data.glossary) ? (data.glossary as unknown[]).map(String) : []

  const config: AppConfig = {
    hotkey: typeof data.hotkey === 'string' ? data.hotkey : 'right alt',
    start_with_windows: data.start_with_windows === true,
    stt,
    llm,
    glossary,
  }

  // 开发模式下强制使用代码中的最新提示词。
  if (devMode) config.llm.prompt = DEFAULT_LLM_PROMPT
  return config
}

export function saveConfig(config: AppConfig, file: string = CONFIG_FILE): void {
  mkdirSync(dirname(file), { recursive: true })
  writeFileSync(file, JSON.stringify(config, null, 2), 'utf-8')
}

export function loadConfig(file: string = CONFIG_FILE, devMode: boolean = isDevMode()): AppConfig {
  if (!existsSync(file)) {
    const cfg = defaultConfig()
    saveConfig(cfg, file)
    return cfg
  }
  let config: AppConfig
  try {
    const data = JSON.parse(readFileSync(file, 'utf-8')) as RawObj
    config = migrateConfig(data, devMode)
  } catch {
    config = defaultConfig()
    if (devMode) config.llm.prompt = DEFAULT_LLM_PROMPT
  }
  // 规范化回写（与旧版一致：load 末尾总是 save）。
  saveConfig(config, file)
  return config
}

/** 组装完整 LLM system prompt（基础 prompt + 用户术语表）。 */
export function buildLlmSystemPrompt(config: AppConfig): string {
  const parts = [config.llm.prompt]
  if (config.glossary.length > 0) {
    const terms = config.glossary.join('、')
    parts.push(
      '## 用户术语表\n' +
        '以下是用户的常用专有名词，请保留这些词的原始写法；' +
        '在 STT 输出中遇到近音误识时，按此表还原：\n' +
        terms,
    )
  }
  return parts.join('\n\n')
}

/** 组装 STT prompt：把术语嵌入自然句送给 Whisper（OpenAI cookbook 推荐格式）。 */
export function buildSttPrompt(config: AppConfig): string {
  if (config.glossary.length === 0) return ''
  const terms = config.glossary.join('、')
  return `本次内容涉及以下术语：${terms}。以下是普通话的句子。`
}
