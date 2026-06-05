import { useStore } from '../store'

export default function General(): JSX.Element {
  const hotkey = useStore((s) => s.hotkey)
  const capturing = useStore((s) => s.capturing)
  const setCapturing = useStore((s) => s.setCapturing)
  const startWithWindows = useStore((s) => s.startWithWindows)
  const setStartWithWindows = useStore((s) => s.setStartWithWindows)

  const startCapture = (): void => {
    setCapturing(true)
    void window.api.startHotkeyCapture()
  }

  return (
    <>
      <div className="px-8 pb-6 pt-8">
        <h2 className="text-2xl font-bold tracking-tight text-primary">General</h2>
        <p className="mt-1 text-sm text-text-muted">Configure basic application behavior.</p>
      </div>
      <div className="custom-scrollbar flex flex-1 flex-col gap-4 overflow-y-auto px-8 pb-20">
        <div className="flex items-center justify-between rounded-lg border border-border-gray p-5">
          <div className="flex flex-col gap-0.5">
            <h3 className="text-sm font-semibold text-primary">Global Hotkey</h3>
            <p className="text-xs text-text-muted">Press to start/stop dictation</p>
          </div>
          <button
            onClick={startCapture}
            className={`hotkey-btn rounded border border-border-gray bg-white px-4 py-1.5 text-xs font-medium uppercase tracking-tight text-primary shadow-sm transition-colors hover:bg-neutral-50 ${
              capturing ? 'listening' : ''
            }`}
          >
            {capturing ? 'Press a key...' : hotkey}
          </button>
        </div>
        <div className="flex items-center justify-between rounded-lg border border-border-gray p-5">
          <div className="flex flex-col gap-0.5">
            <h3 className="text-sm font-semibold text-primary">Start with Windows</h3>
            <p className="text-xs text-text-muted">Launch automatically on login</p>
          </div>
          <label className="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              className="peer sr-only"
              checked={startWithWindows}
              onChange={(e) => setStartWithWindows(e.target.checked)}
            />
            <div className="peer h-6 w-11 rounded-full bg-border-gray after:absolute after:start-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-primary peer-checked:after:translate-x-full peer-checked:after:border-white peer-focus:outline-none"></div>
          </label>
        </div>
      </div>
    </>
  )
}
