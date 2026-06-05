import { useStore } from '../store'
import { findProvider } from '../lib/providers'

export default function Stt(): JSX.Element {
  const sttProviders = useStore((s) => s.sttProviders)
  const activeSttProviderId = useStore((s) => s.activeSttProviderId)
  const activeSttModel = useStore((s) => s.activeSttModel)
  const setSttActiveProvider = useStore((s) => s.setSttActiveProvider)
  const setSttActiveModel = useStore((s) => s.setSttActiveModel)
  const openModal = useStore((s) => s.openModal)
  const deleteProvider = useStore((s) => s.deleteProvider)

  const activeProvider = findProvider(sttProviders, activeSttProviderId)
  const models = activeProvider?.models ?? []

  const onDelete = (id: string): void => {
    if (window.confirm('Are you sure you want to delete this provider?')) void deleteProvider('stt', id)
  }

  return (
    <>
      <header className="flex items-center justify-between px-8 pb-6 pt-8">
        <h2 className="text-2xl font-bold tracking-tight text-primary">Speech-to-Text</h2>
      </header>
      <div className="custom-scrollbar flex flex-1 flex-col gap-8 overflow-y-auto px-8 pb-20">
        <div className="grid grid-cols-2 gap-4 rounded-xl border border-gray-200 bg-white p-5">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-primary">Active Provider</label>
            <div className="relative">
              <select
                value={activeSttProviderId}
                onChange={(e) => setSttActiveProvider(e.target.value)}
                className="h-11 w-full cursor-pointer appearance-none rounded-lg border border-border-gray bg-white pl-4 pr-10 text-sm text-primary outline-none transition-all focus:border-primary focus:ring-0"
              >
                {sttProviders.length === 0 ? (
                  <option value="">No providers</option>
                ) : (
                  sttProviders.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))
                )}
              </select>
              <span className="material-symbols-outlined pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                expand_more
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-primary">Active Model</label>
            <div className="relative">
              <select
                value={activeSttModel}
                onChange={(e) => setSttActiveModel(e.target.value)}
                className="h-11 w-full cursor-pointer appearance-none rounded-lg border border-border-gray bg-white pl-4 pr-10 text-sm text-primary outline-none transition-all focus:border-primary focus:ring-0"
              >
                {models.length === 0 ? (
                  <option value="">No models</option>
                ) : (
                  models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))
                )}
              </select>
              <span className="material-symbols-outlined pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                expand_more
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-primary">Manage Providers</h3>
            <button
              onClick={() => openModal('stt', null)}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-800"
            >
              <span className="material-symbols-outlined text-[18px]">add</span>
              New Provider
            </button>
          </div>
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase tracking-wider text-text-muted">
                <tr>
                  <th className="px-6 py-3 font-medium">Provider</th>
                  <th className="px-6 py-3 font-medium">Base URL</th>
                  <th className="px-6 py-3 font-medium">Models</th>
                  <th className="px-6 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sttProviders.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                      No providers configured. Click "New Provider" to add one.
                    </td>
                  </tr>
                ) : (
                  sttProviders.map((p) => (
                    <tr key={p.id} className="group transition-colors hover:bg-gray-50">
                      <td className="whitespace-nowrap px-6 py-4">
                        <div className="font-semibold text-primary">{p.name}</div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 font-mono text-xs text-gray-500">
                        {p.base_url}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1">
                          {p.models.length === 0 ? (
                            <span className="text-xs italic text-gray-400">No models</span>
                          ) : (
                            p.models.map((m) => (
                              <span
                                key={m}
                                className="inline-flex items-center rounded border border-gray-200 bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-800"
                              >
                                {m}
                              </span>
                            ))
                          )}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium">
                        <div className="flex items-center justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                          <button
                            onClick={() => openModal('stt', p.id)}
                            title="Edit"
                            className="p-1 text-gray-400 transition-colors hover:text-primary"
                          >
                            <span className="material-symbols-outlined text-[18px]">edit</span>
                          </button>
                          <button
                            onClick={() => onDelete(p.id)}
                            title="Delete"
                            className="p-1 text-gray-400 transition-colors hover:text-red-600"
                          >
                            <span className="material-symbols-outlined text-[18px]">delete</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  )
}
