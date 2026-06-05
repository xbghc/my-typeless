import { useEffect, useState } from 'react'
import { useStore } from '../store'
import type { Candidate } from '@shared/types'

export default function Glossary(): JSX.Element {
  const glossary = useStore((s) => s.glossary)
  const addGlossary = useStore((s) => s.addGlossary)
  const removeGlossaryAt = useStore((s) => s.removeGlossaryAt)

  const [input, setInput] = useState('')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [candidates, setCandidates] = useState<Candidate[]>([])

  useEffect(() => {
    window.api.getGlossaryCandidates(3).then(setCandidates).catch(() => setCandidates([]))
  }, [])

  const add = (): void => {
    if (input.trim()) {
      addGlossary(input)
      setInput('')
    }
  }

  const toggle = (i: number): void => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  const deleteSelected = (): void => {
    if (selected.size === 0) return
    removeGlossaryAt([...selected])
    setSelected(new Set())
  }

  const acceptCandidate = async (term: string): Promise<void> => {
    await window.api.acceptGlossaryCandidate(term)
    addGlossary(term)
    setCandidates((prev) => prev.filter((c) => c.term !== term))
  }

  const dismissCandidate = async (term: string): Promise<void> => {
    await window.api.dismissGlossaryCandidate(term)
    setCandidates((prev) => prev.filter((c) => c.term !== term))
  }

  return (
    <>
      <header className="px-8 pb-4 pt-8">
        <h2 className="text-2xl font-bold tracking-tight text-primary">Glossary</h2>
        <p className="mt-1 text-sm text-text-muted">
          Terminology for accurate speech recognition and text refinement.
        </p>
      </header>

      <section className="px-8 py-4">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') add()
            }}
            placeholder="Enter a term, e.g. gRPC"
            className="h-10 flex-1 rounded-lg border border-border-gray bg-white px-4 text-sm text-primary outline-none transition-all placeholder:text-placeholder-gray focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <button
            onClick={add}
            className="flex h-10 items-center gap-2 rounded-lg bg-primary px-5 text-sm font-bold text-white transition-colors hover:bg-zinc-800"
          >
            <span className="material-symbols-outlined text-base">add</span>
            Add
          </button>
        </div>
      </section>

      {candidates.length > 0 && (
        <section className="px-8 pb-2">
          <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-text-muted">
            Suggested terms
          </p>
          <div className="flex flex-wrap gap-2">
            {candidates.map((c) => (
              <div
                key={c.term}
                className="inline-flex items-center gap-1.5 rounded-full border border-border-gray bg-neutral-50 py-1 pl-3 pr-1.5 text-sm"
              >
                <span className="font-medium text-primary">{c.term}</span>
                <span className="text-[10px] text-text-muted">×{c.count}</span>
                <button
                  onClick={() => void acceptCandidate(c.term)}
                  title="Add to glossary"
                  className="flex items-center text-gray-400 hover:text-green-600"
                >
                  <span className="material-symbols-outlined text-[16px]">add_circle</span>
                </button>
                <button
                  onClick={() => void dismissCandidate(c.term)}
                  title="Dismiss"
                  className="flex items-center text-gray-400 hover:text-red-500"
                >
                  <span className="material-symbols-outlined text-[16px]">cancel</span>
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="flex min-h-0 flex-1 flex-col px-8 pb-20">
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-border-gray bg-white">
          <div className="custom-scrollbar flex-1 overflow-y-auto">
            {glossary.length === 0 ? (
              <p className="py-8 text-center text-sm text-text-muted">No terms added yet.</p>
            ) : (
              glossary.map((term, i) => (
                <div
                  key={`${term}-${i}`}
                  onClick={() => toggle(i)}
                  className={`group flex items-center border-b border-border-gray px-4 py-3 transition-colors hover:bg-neutral-50 ${
                    selected.has(i) ? 'bg-neutral-50' : ''
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(i)}
                    onChange={() => toggle(i)}
                    onClick={(e) => e.stopPropagation()}
                    className="size-4 cursor-pointer rounded border-border-gray text-primary focus:ring-0"
                  />
                  <span className="ml-4 text-sm font-medium text-primary">{term}</span>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="flex items-center justify-between py-3">
          <span className="text-[12px] font-medium text-text-muted">{glossary.length} term(s)</span>
          <button
            onClick={deleteSelected}
            className="flex items-center gap-1 text-[12px] font-bold text-text-muted hover:text-primary"
          >
            <span className="material-symbols-outlined text-base">delete</span>
            Delete Selected
          </button>
        </div>
      </section>
    </>
  )
}
