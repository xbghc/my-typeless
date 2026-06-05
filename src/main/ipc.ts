// 注册所有 ipcMain.handle，1:1 对应旧版 webview_api.py 暴露的方法。
import { app, ipcMain } from 'electron'
import OpenAI from 'openai'
import Anthropic from '@anthropic-ai/sdk'
import { IPC } from '@shared/ipc-channels'
import type { AppConfig, PlaygroundResult, ProviderTestPayload, TestResult } from '@shared/types'
import { buildLlmSystemPrompt, migrateConfig, saveConfig } from './config'
import { LLMClient } from './llmClient'
import type { HistoryStore } from './history'
import type { CandidateStore } from './candidates'

// 允许的热键列表（供前端下拉），逐字对应 webview_api.ALLOWED_HOTKEYS。
export const ALLOWED_HOTKEYS = [
  'left alt',
  'right alt',
  'alt',
  'left ctrl',
  'right ctrl',
  'ctrl',
  'left shift',
  'right shift',
  'shift',
  'left windows',
  'right windows',
  'caps lock',
  'tab',
  'space',
  'f1',
  'f2',
  'f3',
  'f4',
  'f5',
  'f6',
  'f7',
  'f8',
  'f9',
  'f10',
  'f11',
  'f12',
]

export interface IpcDeps {
  getConfig: () => AppConfig
  setConfig: (config: AppConfig) => void
  history: HistoryStore
  candidates: CandidateStore
  onConfigSaved?: (config: AppConfig) => void
  hideSettings: () => void
  startHotkeyCapture: () => void
}

async function runTest(deps: IpcDeps, rawText: string): Promise<PlaygroundResult> {
  try {
    const cfg = deps.getConfig()
    const client = new LLMClient(cfg.llm)
    const refined = await client.refine(rawText, buildLlmSystemPrompt(cfg))
    if (rawText.trim() && refined) deps.history.add(rawText, refined)
    return { success: true, result: refined }
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : String(e) }
  }
}

async function testConnection(payload?: ProviderTestPayload): Promise<TestResult> {
  try {
    if (!payload) return { success: false, error: 'No credentials provided for testing' }
    const { base_url, api_key, model, provider_type = 'openai' } = payload
    if (!api_key || !model) {
      return { success: false, error: 'API Key and Model are required for testing' }
    }
    if (provider_type === 'anthropic') {
      const client = new Anthropic({ apiKey: api_key, baseURL: base_url || undefined })
      await client.messages.create({
        model,
        max_tokens: 1,
        messages: [{ role: 'user', content: 'test' }],
      })
    } else {
      if (!base_url) {
        return { success: false, error: 'Base URL is required for OpenAI compatible providers' }
      }
      const client = new OpenAI({ baseURL: base_url, apiKey: api_key })
      await client.models.retrieve(model)
    }
    return { success: true }
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : String(e) }
  }
}

export function registerIpc(deps: IpcDeps): void {
  ipcMain.handle(IPC.CONFIG_GET, () => deps.getConfig())

  ipcMain.handle(IPC.CONFIG_SAVE, (_e, data: AppConfig) => {
    try {
      // migrateConfig(devMode=false) 规范化前端数据但不覆盖用户 prompt。
      const config = migrateConfig(data as unknown as Record<string, unknown>, false)
      saveConfig(config)
      deps.setConfig(config)
      deps.onConfigSaved?.(config)
      return { success: true }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : String(e) }
    }
  })

  ipcMain.handle(IPC.HISTORY_GET, (_e, offset: number, limit: number) =>
    deps.history.getPage(offset, limit),
  )
  ipcMain.handle(IPC.HISTORY_CLEAR, () => {
    deps.history.clear()
    return { success: true }
  })

  ipcMain.handle(IPC.PLAYGROUND_RUN, (_e, rawText: string) => runTest(deps, rawText))
  ipcMain.handle(IPC.STT_TEST, (_e, payload?: ProviderTestPayload) => testConnection(payload))
  ipcMain.handle(IPC.LLM_TEST, (_e, payload?: ProviderTestPayload) => testConnection(payload))

  ipcMain.handle(IPC.APP_VERSION, () => app.getVersion())
  ipcMain.handle(IPC.HOTKEY_ALLOWED, () => ALLOWED_HOTKEYS)
  ipcMain.handle(IPC.HOTKEY_CAPTURE_START, () => deps.startHotkeyCapture())
  ipcMain.handle(IPC.WINDOW_CLOSE, () => deps.hideSettings())

  ipcMain.handle(IPC.CANDIDATES_GET, (_e, minCount = 3) => deps.candidates.get(minCount))
  ipcMain.handle(IPC.CANDIDATES_ACCEPT, (_e, term: string) => {
    if (!term) return { success: false, error: 'term is empty' }
    const cfg = deps.getConfig()
    if (!cfg.glossary.includes(term)) {
      cfg.glossary = [...cfg.glossary, term]
      saveConfig(cfg)
      deps.setConfig(cfg)
      deps.onConfigSaved?.(cfg)
    }
    deps.candidates.accept(term)
    return { success: true }
  })
  ipcMain.handle(IPC.CANDIDATES_DISMISS, (_e, term: string) => {
    if (!term) return { success: false, error: 'term is empty' }
    deps.candidates.dismiss(term)
    return { success: true }
  })
}
