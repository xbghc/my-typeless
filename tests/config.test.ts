import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import {
  DEFAULT_LLM_PROMPT,
  buildLlmSystemPrompt,
  buildSttPrompt,
  defaultConfig,
  loadConfig,
  saveConfig,
} from '@main/config'

let dir: string
let file: string

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'mt-config-'))
  file = join(dir, 'config.json')
})
afterEach(() => {
  rmSync(dir, { recursive: true, force: true })
})

describe('config load/migrate', () => {
  it('migrates legacy provider fields', () => {
    writeFileSync(
      file,
      JSON.stringify({
        hotkey: 'f8',
        start_with_windows: true,
        stt: {
          base_url: 'https://legacy-stt.example/v1',
          api_key: 'stt-key',
          model: 'whisper-legacy',
          language: 'zh',
        },
        llm: {
          base_url: 'https://legacy-llm.example/v1',
          api_key: 'llm-key',
          model: 'legacy-chat',
          prompt: 'custom prompt',
        },
        glossary: ['MyTypeless', 'Whisper'],
      }),
    )
    const cfg = loadConfig(file, false)
    expect(cfg.hotkey).toBe('f8')
    expect(cfg.start_with_windows).toBe(true)
    expect(cfg.stt.active_provider_id).toBe('migrated-stt')
    expect(cfg.stt.active_model).toBe('whisper-legacy')
    expect(cfg.stt.providers[0].base_url).toBe('https://legacy-stt.example/v1')
    expect(cfg.stt.providers[0].models).toEqual(['whisper-legacy'])
    expect(cfg.stt.language).toBe('zh')
    expect(cfg.llm.active_provider_id).toBe('migrated-llm')
    expect(cfg.llm.active_model).toBe('legacy-chat')
    expect(cfg.llm.providers[0].base_url).toBe('https://legacy-llm.example/v1')
    expect(cfg.llm.prompt).toBe('custom prompt')
    const stt = buildSttPrompt(cfg)
    expect(stt).toContain('MyTypeless')
    expect(stt).toContain('Whisper')
  })

  it('falls back to defaults on invalid json and rewrites file', () => {
    writeFileSync(file, '{ invalid json')
    const cfg = loadConfig(file, false)
    expect(cfg.hotkey).toBe('right alt')
    expect(cfg.stt.active_provider_id).toBe('default-stt')
    expect(cfg.llm.active_provider_id).toBe('default-llm')
    expect(cfg.llm.prompt).toBe(DEFAULT_LLM_PROMPT)
    const saved = JSON.parse(readFileSync(file, 'utf-8'))
    expect(saved.hotkey).toBe('right alt')
  })

  it('creates default config when file missing', () => {
    expect(existsSync(file)).toBe(false)
    const cfg = loadConfig(file, false)
    expect(cfg.hotkey).toBe('right alt')
    expect(existsSync(file)).toBe(true)
  })

  it('save and reload roundtrip', () => {
    const cfg = defaultConfig()
    cfg.hotkey = 'f12'
    cfg.glossary = ['CSS', 'DOM', 'Shadow DOM']
    saveConfig(cfg, file)
    const reloaded = loadConfig(file, false)
    expect(reloaded.hotkey).toBe('f12')
    expect(reloaded.glossary).toEqual(['CSS', 'DOM', 'Shadow DOM'])
  })

  it('preserves modern providers format', () => {
    writeFileSync(
      file,
      JSON.stringify({
        hotkey: 'f12',
        stt: {
          providers: [
            {
              id: 'groq',
              name: 'Groq',
              base_url: 'https://api.groq.com/openai/v1',
              api_key: 'k1',
              models: ['whisper-large-v3'],
              provider_type: 'openai',
            },
          ],
          active_provider_id: 'groq',
          active_model: 'whisper-large-v3',
          language: 'zh',
        },
        llm: {
          providers: [
            {
              id: 'anthropic',
              name: 'Anthropic',
              base_url: '',
              api_key: 'k2',
              models: ['claude-sonnet-4-6'],
              provider_type: 'anthropic',
            },
          ],
          active_provider_id: 'anthropic',
          active_model: 'claude-sonnet-4-6',
          prompt: 'custom user prompt',
        },
        glossary: ['CSS', 'DOM'],
      }),
    )
    const cfg = loadConfig(file, false)
    expect(cfg.stt.active_provider_id).toBe('groq')
    expect(cfg.stt.providers[0].provider_type).toBe('openai')
    expect(cfg.llm.active_provider_id).toBe('anthropic')
    expect(cfg.llm.providers[0].provider_type).toBe('anthropic')
    expect(cfg.llm.prompt).toBe('custom user prompt')
    expect(cfg.glossary).toEqual(['CSS', 'DOM'])
  })

  it('dev mode overrides user prompt', () => {
    writeFileSync(file, JSON.stringify({ llm: { prompt: '用户自定义 prompt' } }))
    const cfg = loadConfig(file, true)
    expect(cfg.llm.prompt).toBe(DEFAULT_LLM_PROMPT)
  })

  it('default stt language is zh', () => {
    const cfg = loadConfig(file, false)
    expect(cfg.stt.language).toBe('zh')
  })

  it('invalid glossary type falls back to empty list', () => {
    writeFileSync(file, JSON.stringify({ glossary: 'not a list' }))
    const cfg = loadConfig(file, false)
    expect(cfg.glossary).toEqual([])
  })
})

describe('prompt builders', () => {
  it('embeds glossary in natural sentence for stt', () => {
    const cfg = defaultConfig()
    cfg.glossary = ['CSS', 'DOM', 'Shadow DOM']
    const prompt = buildSttPrompt(cfg)
    expect(prompt).toContain('CSS')
    expect(prompt).toContain('DOM')
    expect(prompt).toContain('Shadow DOM')
    expect(prompt.includes('术语') || prompt.includes('句子')).toBe(true)
  })

  it('stt prompt empty when no glossary', () => {
    expect(buildSttPrompt(defaultConfig())).toBe('')
  })

  it('appends glossary section to llm system prompt', () => {
    const cfg = defaultConfig()
    cfg.glossary = ['CSS', 'DOM']
    const prompt = buildLlmSystemPrompt(cfg)
    expect(prompt).toContain(cfg.llm.prompt)
    expect(prompt).toContain('用户术语表')
    expect(prompt).toContain('CSS')
    expect(prompt).toContain('DOM')
  })

  it('no glossary section when empty', () => {
    const cfg = defaultConfig()
    expect(cfg.glossary).toEqual([])
    expect(buildLlmSystemPrompt(cfg)).toBe(cfg.llm.prompt)
  })
})
