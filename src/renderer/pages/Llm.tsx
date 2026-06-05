import { useState } from 'react'
import { useStore } from '../store'

interface TestStatus {
  dot: string
  text: string
}

export default function Llm(): JSX.Element {
  const llmUrl = useStore((s) => s.llmUrl)
  const llmKey = useStore((s) => s.llmKey)
  const llmModel = useStore((s) => s.llmModel)
  const llmPrompt = useStore((s) => s.llmPrompt)
  const setLlmUrl = useStore((s) => s.setLlmUrl)
  const setLlmKey = useStore((s) => s.setLlmKey)
  const setLlmModel = useStore((s) => s.setLlmModel)
  const setLlmPrompt = useStore((s) => s.setLlmPrompt)

  const [showKey, setShowKey] = useState(false)
  const [testInput, setTestInput] = useState('')
  const [testOutput, setTestOutput] = useState('')
  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState<TestStatus>({ dot: 'bg-gray-300', text: 'Ready' })

  const run = async (): Promise<void> => {
    const raw = testInput.trim()
    if (!raw) {
      setStatus({ dot: 'bg-red-400', text: 'Enter text first' })
      return
    }
    setRunning(true)
    setTestOutput('')
    setStatus({ dot: 'bg-primary', text: 'Calling LLM...' })
    try {
      const result = await window.api.runTest(raw, null)
      if (result.success) {
        setTestOutput(result.result || '')
        setStatus({ dot: 'bg-green-500', text: 'Done' })
      } else {
        setStatus({ dot: 'bg-red-400', text: `Error: ${result.error}` })
      }
    } catch (e) {
      setStatus({ dot: 'bg-red-400', text: `Error: ${e}` })
    } finally {
      setRunning(false)
    }
  }

  const copy = (): void => {
    if (testOutput) void navigator.clipboard.writeText(testOutput)
  }

  const active = !!llmKey

  return (
    <>
      <header className="flex shrink-0 items-center justify-between border-b border-gray-100 px-8 py-5">
        <div className="flex flex-col">
          <h2 className="text-xl font-bold text-primary">Text Refinement</h2>
          <p className="text-xs text-gray-400">Configure your AI model settings</p>
        </div>
        <span
          className={
            active
              ? 'rounded bg-primary px-2.5 py-1 text-[10px] font-bold tracking-widest text-white'
              : 'rounded-full bg-border-gray px-2.5 py-1 text-[10px] font-bold tracking-wider text-primary'
          }
        >
          {active ? 'ACTIVE' : 'INACTIVE'}
        </span>
      </header>
      <div className="custom-scrollbar flex-1 overflow-y-auto pb-20">
        <section className="space-y-5 px-8 py-6">
          <div className="mb-1 flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-gray-400">api</span>
            <h3 className="text-sm font-bold uppercase tracking-wide text-gray-800">API Config</h3>
          </div>
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 ml-0.5 block text-xs font-bold text-gray-500">API Base URL</label>
              <input
                value={llmUrl}
                onChange={(e) => setLlmUrl(e.target.value)}
                placeholder="https://api.deepseek.com/v1"
                className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition-all focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label className="mb-1.5 ml-0.5 block text-xs font-bold text-gray-500">API Key</label>
              <div className="relative">
                <input
                  value={llmKey}
                  onChange={(e) => setLlmKey(e.target.value)}
                  type={showKey ? 'text' : 'password'}
                  placeholder="sk-..."
                  className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 pr-10 text-sm text-gray-800 outline-none transition-all focus:border-primary focus:ring-1 focus:ring-primary"
                />
                <button
                  onClick={() => setShowKey((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <span className="material-symbols-outlined text-[18px]">
                    {showKey ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>
            <div>
              <label className="mb-1.5 ml-0.5 block text-xs font-bold text-gray-500">Model Name</label>
              <input
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                placeholder="deepseek-chat"
                className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition-all focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>
        </section>
        <hr className="mx-8 border-gray-100" />
        <section className="px-8 py-6">
          <div className="mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-gray-400">terminal</span>
            <h3 className="text-sm font-bold uppercase tracking-wide text-gray-800">System Prompt</h3>
          </div>
          <textarea
            value={llmPrompt}
            onChange={(e) => setLlmPrompt(e.target.value)}
            rows={6}
            placeholder="Define how the AI should refine your text..."
            className="w-full resize-none rounded-lg border border-gray-200 bg-white p-3 text-sm leading-relaxed text-gray-800 outline-none transition-all focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </section>
        <hr className="mx-8 border-gray-100" />
        <section className="space-y-4 px-8 py-6">
          <div className="mb-2 flex flex-col gap-0.5">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-gray-400">science</span>
              <h3 className="text-sm font-bold uppercase tracking-wide text-gray-800">Playground</h3>
            </div>
            <p className="ml-6 text-[11px] text-gray-400">Test refinement with current settings</p>
          </div>
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-bold text-gray-500">Raw Input</label>
              <textarea
                value={testInput}
                onChange={(e) => setTestInput(e.target.value)}
                rows={3}
                placeholder="Paste unrefined transcript here..."
                className="w-full resize-none rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-800 outline-none transition-all focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => void run()}
                disabled={running}
                className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2 text-xs font-bold text-white shadow-sm transition-transform active:scale-95"
              >
                <span
                  className={`material-symbols-outlined text-[16px] ${running ? 'animate-spin' : ''}`}
                >
                  {running ? 'progress_activity' : 'play_arrow'}
                </span>
                {running ? 'Running...' : 'Run'}
              </button>
            </div>
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label className="text-xs font-bold text-gray-500">Refined Output</label>
                <button
                  onClick={copy}
                  className="text-[10px] font-bold uppercase tracking-tighter text-primary hover:underline"
                >
                  Copy
                </button>
              </div>
              <textarea
                value={testOutput}
                readOnly
                rows={3}
                placeholder="The refined text will appear here..."
                className="w-full resize-none rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm italic text-gray-500 outline-none"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 pt-2 text-gray-400">
            <div className={`h-2 w-2 rounded-full ${status.dot}`}></div>
            <span className="text-[10px] font-bold uppercase tracking-widest">{status.text}</span>
          </div>
        </section>
      </div>
    </>
  )
}
