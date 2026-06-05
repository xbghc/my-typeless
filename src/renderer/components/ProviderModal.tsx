import { useState } from 'react'
import { useStore } from '../store'
import { generateId } from '../lib/providers'
import type { ProviderType } from '@shared/types'

type TestState = 'idle' | 'testing' | 'success'

export default function ProviderModal(): JSX.Element {
  const modal = useStore((s) => s.modal)
  const closeModal = useStore((s) => s.closeModal)
  const saveProvider = useStore((s) => s.saveProvider)
  const sttProviders = useStore((s) => s.sttProviders)
  const llmProviders = useStore((s) => s.llmProviders)

  const kind = modal?.kind ?? 'stt'
  const editingId = modal?.editingId ?? null
  const providers = kind === 'stt' ? sttProviders : llmProviders
  const editing = editingId ? providers.find((p) => p.id === editingId) : null

  const [apiType, setApiType] = useState<ProviderType>(editing?.provider_type ?? 'openai')
  const [name, setName] = useState(editing?.name ?? '')
  const [url, setUrl] = useState(editing?.base_url ?? '')
  const [key, setKey] = useState(editing?.api_key ?? '')
  const [showKey, setShowKey] = useState(false)
  const [models, setModels] = useState<string[]>(editing ? [...editing.models] : [])
  const [modelInput, setModelInput] = useState('')
  const [test, setTest] = useState<TestState>('idle')

  const addModel = (): void => {
    const v = modelInput.trim()
    if (v && !models.includes(v)) {
      setModels([...models, v])
      setModelInput('')
    }
  }

  const onModelKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addModel()
    } else if (e.key === 'Backspace' && modelInput === '' && models.length > 0) {
      setModels(models.slice(0, -1))
    }
  }

  const testConnection = async (): Promise<void> => {
    if ((!url.trim() && apiType !== 'anthropic') || !key.trim()) {
      window.alert('API Key (and Base URL for OpenAI) are required to test connection.')
      return
    }
    if (models.length === 0) {
      window.alert('At least one model must be added to test connection.')
      return
    }
    setTest('testing')
    try {
      const payload = {
        base_url: url.trim(),
        api_key: key.trim(),
        model: models[0],
        provider_type: apiType,
      }
      const result =
        kind === 'stt'
          ? await window.api.testSttConnection(payload)
          : await window.api.testLlmConnection(payload)
      if (result.success) {
        setTest('success')
        setTimeout(() => setTest('idle'), 2000)
      } else {
        window.alert('Connection failed: ' + (result.error || 'Unknown'))
        setTest('idle')
      }
    } catch (e) {
      window.alert('Connection failed: ' + e)
      setTest('idle')
    }
  }

  const save = async (): Promise<void> => {
    if (!name.trim()) {
      window.alert('Provider Name is required.')
      return
    }
    // Anthropic 走 SDK 内置官方端点，Base URL 可留空（与 Test Connection 的校验一致）。
    if (apiType !== 'anthropic' && !url.trim()) {
      window.alert('Base URL is required for OpenAI compatible providers.')
      return
    }
    await saveProvider(kind, {
      id: editingId || generateId(),
      name: name.trim(),
      base_url: url.trim(),
      api_key: key.trim(),
      models: [...models],
      provider_type: apiType,
    })
    closeModal()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-[480px] overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-6 py-4">
          <h3 className="text-lg font-bold text-primary">
            {editingId ? 'Edit Provider' : 'Add Provider'}
          </h3>
          <button onClick={closeModal} className="text-gray-400 transition-colors hover:text-gray-600">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="flex flex-col gap-5 p-6">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-primary">Type</label>
            <select
              value={apiType}
              onChange={(e) => setApiType(e.target.value as ProviderType)}
              className="h-11 w-full cursor-pointer rounded-lg border border-border-gray bg-white px-4 text-sm text-primary outline-none transition-all focus:border-primary focus:ring-0"
            >
              <option value="openai">OpenAI (Compatible)</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-primary">Provider Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Minimax"
              className="h-11 w-full rounded-lg border border-border-gray bg-white px-4 text-sm text-primary outline-none transition-all placeholder:text-placeholder-gray focus:border-primary focus:ring-0"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-primary">Base URL</label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://api.minimax.chat/v1"
              className="h-11 w-full rounded-lg border border-border-gray bg-white px-4 text-sm text-primary outline-none transition-all placeholder:text-placeholder-gray focus:border-primary focus:ring-0"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-primary">API Key</label>
            <div className="relative">
              <input
                value={key}
                onChange={(e) => setKey(e.target.value)}
                type={showKey ? 'text' : 'password'}
                placeholder="sk-..."
                className="h-11 w-full rounded-lg border border-border-gray bg-white px-4 pr-10 text-sm text-primary outline-none transition-all placeholder:text-placeholder-gray focus:border-primary focus:ring-0"
              />
              <button
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-primary"
              >
                <span className="material-symbols-outlined text-[20px]">
                  {showKey ? 'visibility_off' : 'visibility'}
                </span>
              </button>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-primary">Models</label>
            <div
              onClick={() => document.getElementById('modalModelInput')?.focus()}
              className="flex min-h-[44px] w-full cursor-text flex-wrap items-center gap-2 rounded-lg border border-border-gray bg-white p-2 transition-all focus-within:border-primary"
            >
              {models.map((m, i) => (
                <div
                  key={`${m}-${i}`}
                  className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-gray-100 px-2.5 py-1 text-sm font-medium text-primary"
                >
                  <span>{m}</span>
                  <button
                    onClick={() => setModels(models.filter((_, idx) => idx !== i))}
                    className="flex items-center justify-center rounded-full p-0.5 text-gray-400 hover:text-red-500"
                  >
                    <span className="material-symbols-outlined text-[14px]">close</span>
                  </button>
                </div>
              ))}
              <input
                id="modalModelInput"
                value={modelInput}
                onChange={(e) => setModelInput(e.target.value)}
                onKeyDown={onModelKeyDown}
                placeholder="Add model & press Enter"
                className="h-7 min-w-[100px] flex-1 border-none bg-transparent px-1 text-sm text-primary outline-none placeholder:text-placeholder-gray focus:ring-0"
              />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-gray-100 bg-gray-50 px-6 py-4">
          <button
            onClick={() => void testConnection()}
            disabled={test === 'testing'}
            className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-primary transition-colors hover:bg-gray-50 disabled:opacity-50"
          >
            {test === 'success' ? (
              <>
                <span className="material-symbols-outlined text-[16px] text-green-500">
                  check_circle
                </span>
                Success
              </>
            ) : test === 'testing' ? (
              <>
                <span className="material-symbols-outlined animate-spin text-[16px]">
                  progress_activity
                </span>
                Testing...
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[16px]">link</span>
                Test Connection
              </>
            )}
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={closeModal}
              className="rounded-lg px-5 py-2 text-sm font-semibold text-gray-600 transition-colors hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              onClick={() => void save()}
              className="rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-800"
            >
              Save Provider
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
