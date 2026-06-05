import { useEffect, useRef, useState } from 'react'
import type { HistoryEntry } from '@shared/types'

export default function History(): JSX.Element {
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [empty, setEmpty] = useState(false)
  const offset = useRef(0)
  const hasMore = useRef(true)
  const loading = useRef(false)
  const listRef = useRef<HTMLDivElement>(null)

  const loadMore = async (): Promise<void> => {
    if (loading.current || !hasMore.current) return
    loading.current = true
    try {
      const data = await window.api.getHistory(offset.current, 20)
      const fresh = data.entries ?? []
      hasMore.current = data.has_more
      if (data.next_offset != null) offset.current = data.next_offset
      setEntries((prev) => {
        const merged = [...prev, ...fresh]
        setEmpty(merged.length === 0)
        return merged
      })
    } finally {
      loading.current = false
    }
  }

  useEffect(() => {
    offset.current = 0
    hasMore.current = true
    loading.current = false
    setEntries([])
    setEmpty(false)
    void loadMore()
  }, [])

  const onScroll = (): void => {
    const el = listRef.current
    if (!el) return
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 200) void loadMore()
  }

  const clearAll = async (): Promise<void> => {
    if (!window.confirm('Clear all history entries?')) return
    await window.api.clearHistory()
    offset.current = 0
    hasMore.current = true
    setEntries([])
    setEmpty(true)
  }

  return (
    <>
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-100 px-6">
        <h2 className="text-lg font-bold text-primary">History</h2>
        <button
          onClick={() => void clearAll()}
          className="text-xs font-semibold text-gray-500 transition-colors hover:text-primary"
        >
          Clear All
        </button>
      </header>
      <div
        ref={listRef}
        onScroll={onScroll}
        className="custom-scrollbar flex-1 space-y-4 overflow-y-auto p-6 pb-20"
      >
        {empty ? (
          <p className="py-8 text-center text-sm text-text-muted">No history entries yet.</p>
        ) : (
          entries.map((e, i) => <HistoryCard key={e.id ?? i} entry={e} />)
        )}
      </div>
    </>
  )
}

function HistoryCard({ entry }: { entry: HistoryEntry }): JSX.Element {
  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2">
        <span className="text-[10px] font-medium uppercase tracking-tight text-gray-500">
          {entry.timestamp}
        </span>
      </div>
      <div className="grid min-h-[80px] grid-cols-2">
        <div className="border-r border-gray-100 p-4">
          <label className="mb-2 block text-[10px] font-bold uppercase text-gray-400">Input</label>
          <p className="text-sm leading-relaxed text-gray-600">{entry.raw_input}</p>
        </div>
        <div className="p-4">
          <label className="mb-2 block text-[10px] font-bold uppercase text-gray-400">Output</label>
          <p className="text-sm font-medium leading-relaxed text-primary">{entry.refined_output}</p>
        </div>
      </div>
    </div>
  )
}
