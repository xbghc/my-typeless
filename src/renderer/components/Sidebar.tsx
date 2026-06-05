import { useStore, type PageId } from '../store'

const NAV: { id: PageId; icon: string; label: string }[] = [
  { id: 'general', icon: 'settings', label: 'General' },
  { id: 'stt', icon: 'mic', label: 'Speech-to-Text' },
  { id: 'llm', icon: 'magic_button', label: 'Text Refinement' },
  { id: 'glossary', icon: 'menu_book', label: 'Glossary' },
  { id: 'history', icon: 'history', label: 'History' },
]

export default function Sidebar(): JSX.Element {
  const page = useStore((s) => s.page)
  const setPage = useStore((s) => s.setPage)
  const version = useStore((s) => s.version)

  return (
    <aside className="flex w-[220px] shrink-0 flex-col justify-between border-r border-border-gray bg-white p-4">
      <div className="flex flex-col gap-6">
        <div className="px-2">
          <h1 className="text-lg font-bold leading-none text-primary">My Typeless</h1>
          <p className="mt-1 text-xs text-text-muted">AI Voice Input</p>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => {
            const active = page === item.id
            return (
              <a
                key={item.id}
                onClick={() => setPage(item.id)}
                className={`flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 transition-colors ${
                  active ? 'bg-primary text-white' : 'text-text-muted hover:bg-neutral-100'
                }`}
              >
                <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                <span className="text-sm font-medium">{item.label}</span>
              </a>
            )
          })}
        </nav>
      </div>
      <div className="px-3 py-2">
        <p className="text-[10px] font-medium tracking-wider text-text-muted">v{version}</p>
      </div>
    </aside>
  )
}
