import { create } from 'zustand'
import type { AppConfig, OverlayTheme, ProviderConfig } from '@shared/types'
import {
  findProvider,
  normalizeProviders,
  resolveActiveModel,
  resolveActiveProviderId,
} from './lib/providers'

export type PageId = 'general' | 'stt' | 'llm' | 'glossary' | 'history'
export type ProviderKind = 'stt' | 'llm'

export interface ModalState {
  kind: ProviderKind
  editingId: string | null
}

interface SettingsStore {
  loaded: boolean
  version: string
  page: PageId

  hotkey: string
  capturing: boolean
  startWithWindows: boolean
  overlayEnabled: boolean
  overlayTheme: OverlayTheme
  language: string

  sttProviders: ProviderConfig[]
  activeSttProviderId: string
  activeSttModel: string

  llmProviders: ProviderConfig[]
  activeLlmProviderId: string
  llmUrl: string
  llmKey: string
  llmModel: string
  llmPrompt: string

  glossary: string[]
  modal: ModalState | null

  init: () => Promise<void>
  setPage: (p: PageId) => void

  setHotkey: (h: string) => void
  setCapturing: (c: boolean) => void
  setStartWithWindows: (v: boolean) => void
  setOverlayEnabled: (v: boolean) => void
  setOverlayTheme: (t: OverlayTheme) => void

  setSttActiveProvider: (id: string) => void
  setSttActiveModel: (m: string) => void

  setLlmUrl: (v: string) => void
  setLlmKey: (v: string) => void
  setLlmModel: (v: string) => void
  setLlmPrompt: (v: string) => void

  addGlossary: (term: string) => void
  removeGlossaryAt: (indices: number[]) => void

  openModal: (kind: ProviderKind, editingId: string | null) => void
  closeModal: () => void
  saveProvider: (kind: ProviderKind, provider: ProviderConfig) => Promise<void>
  deleteProvider: (kind: ProviderKind, id: string) => Promise<void>

  collect: () => AppConfig
  save: () => Promise<void>
  apply: () => Promise<void>
}

export const useStore = create<SettingsStore>((set, get) => ({
  loaded: false,
  version: '...',
  page: 'general',
  hotkey: 'right alt',
  capturing: false,
  startWithWindows: false,
  overlayEnabled: true,
  overlayTheme: 'auto',
  language: '',
  sttProviders: [],
  activeSttProviderId: '',
  activeSttModel: '',
  llmProviders: [],
  activeLlmProviderId: '',
  llmUrl: '',
  llmKey: '',
  llmModel: '',
  llmPrompt: '',
  glossary: [],
  modal: null,

  init: async () => {
    const [config, version] = await Promise.all([window.api.getConfig(), window.api.getVersion()])
    const sttProviders = normalizeProviders(config.stt?.providers)
    const activeSttProviderId = resolveActiveProviderId(sttProviders, config.stt?.active_provider_id)
    const activeSttModel = resolveActiveModel(sttProviders, activeSttProviderId, config.stt?.active_model)
    const llmProviders = normalizeProviders(config.llm?.providers)
    const activeLlmProviderId = resolveActiveProviderId(llmProviders, config.llm?.active_provider_id)
    const activeLlmModel = resolveActiveModel(llmProviders, activeLlmProviderId, config.llm?.active_model)
    const activeLlm = findProvider(llmProviders, activeLlmProviderId)
    set({
      loaded: true,
      version,
      hotkey: config.hotkey || 'right alt',
      startWithWindows: !!config.start_with_windows,
      overlayEnabled: config.overlay?.enabled ?? true,
      overlayTheme: config.overlay?.theme ?? 'auto',
      language: config.stt?.language || '',
      sttProviders,
      activeSttProviderId,
      activeSttModel,
      llmProviders,
      activeLlmProviderId,
      llmUrl: activeLlm?.base_url || '',
      llmKey: activeLlm?.api_key || '',
      llmModel: activeLlmModel || '',
      llmPrompt: config.llm?.prompt || '',
      glossary: [...(config.glossary || [])],
    })
  },

  setPage: (page) => set({ page }),
  setHotkey: (hotkey) => set({ hotkey }),
  setCapturing: (capturing) => set({ capturing }),
  setStartWithWindows: (startWithWindows) => set({ startWithWindows }),
  setOverlayEnabled: (overlayEnabled) => set({ overlayEnabled }),
  setOverlayTheme: (overlayTheme) => set({ overlayTheme }),

  setSttActiveProvider: (id) => {
    const provider = findProvider(get().sttProviders, id)
    set({ activeSttProviderId: id, activeSttModel: provider?.models[0] ?? '' })
  },
  setSttActiveModel: (m) => set({ activeSttModel: m }),

  setLlmUrl: (v) => set({ llmUrl: v }),
  setLlmKey: (v) => set({ llmKey: v }),
  setLlmModel: (v) => set({ llmModel: v }),
  setLlmPrompt: (v) => set({ llmPrompt: v }),

  addGlossary: (term) => {
    const t = term.trim()
    const { glossary } = get()
    if (!t || glossary.includes(t)) return
    set({ glossary: [...glossary, t] })
  },
  removeGlossaryAt: (indices) => {
    const drop = new Set(indices)
    set({ glossary: get().glossary.filter((_, i) => !drop.has(i)) })
  },

  openModal: (kind, editingId) => set({ modal: { kind, editingId } }),
  closeModal: () => set({ modal: null }),

  saveProvider: async (kind, provider) => {
    const key = kind === 'stt' ? 'sttProviders' : 'llmProviders'
    const list = [...get()[key]]
    const idx = list.findIndex((p) => p.id === provider.id)
    if (idx >= 0) list[idx] = provider
    else list.push(provider)
    if (kind === 'stt') {
      const activeId = resolveActiveProviderId(list, get().activeSttProviderId)
      set({
        sttProviders: list,
        activeSttProviderId: activeId,
        activeSttModel: resolveActiveModel(list, activeId, get().activeSttModel),
      })
    } else {
      set({ llmProviders: list })
    }
    await get().apply()
  },

  deleteProvider: async (kind, id) => {
    if (kind === 'stt') {
      const list = get().sttProviders.filter((p) => p.id !== id)
      let activeId = get().activeSttProviderId
      if (activeId === id) activeId = list[0]?.id ?? ''
      set({
        sttProviders: list,
        activeSttProviderId: activeId,
        activeSttModel: resolveActiveModel(list, activeId, get().activeSttModel),
      })
    } else {
      const list = get().llmProviders.filter((p) => p.id !== id)
      let activeId = get().activeLlmProviderId
      if (activeId === id) activeId = list[0]?.id ?? ''
      set({ llmProviders: list, activeLlmProviderId: activeId })
    }
    await get().apply()
  },

  collect: () => {
    const s = get()
    const sttProviders = s.sttProviders
    const activeSttProviderId = resolveActiveProviderId(sttProviders, s.activeSttProviderId)
    const activeSttModel = s.activeSttModel || resolveActiveModel(sttProviders, activeSttProviderId, '')

    const llmProviders = s.llmProviders.map((p) => ({ ...p, models: [...p.models] }))
    const activeLlm = findProvider(llmProviders, s.activeLlmProviderId)
    const llmUrl = s.llmUrl.trim()
    const llmKey = s.llmKey.trim()
    const llmModel = s.llmModel.trim()
    if (activeLlm) {
      activeLlm.base_url = llmUrl
      activeLlm.api_key = llmKey
      if (llmModel) activeLlm.models = [llmModel, ...activeLlm.models.filter((m) => m !== llmModel)]
    }
    const activeLlmModel = llmModel || resolveActiveModel(llmProviders, s.activeLlmProviderId, '')

    return {
      hotkey: s.hotkey,
      start_with_windows: s.startWithWindows,
      overlay: { enabled: s.overlayEnabled, theme: s.overlayTheme },
      stt: {
        providers: sttProviders,
        active_provider_id: activeSttProviderId,
        active_model: activeSttModel,
        language: s.language,
      },
      llm: {
        providers: llmProviders,
        active_provider_id: s.activeLlmProviderId,
        active_model: activeLlmModel,
        prompt: s.llmPrompt.trim(),
      },
      glossary: [...s.glossary],
    }
  },

  save: async () => {
    const result = await window.api.saveConfig(get().collect())
    if (result.success) await window.api.closeWindow()
    else window.alert('Save failed: ' + (result.error || 'Unknown error'))
  },

  apply: async () => {
    const result = await window.api.saveConfig(get().collect())
    if (!result.success) window.alert('Save failed: ' + (result.error || 'Unknown error'))
  },
}))
