import { useStore } from '../store'

export default function Footer(): JSX.Element {
  const save = useStore((s) => s.save)

  return (
    <footer className="absolute bottom-0 left-0 right-0 z-10 flex h-16 items-center justify-end gap-3 border-t border-gray-100 bg-white px-8">
      <button
        onClick={() => void window.api.closeWindow()}
        className="rounded-lg border border-border-gray px-5 py-2 text-sm font-medium text-primary transition-colors hover:bg-neutral-50"
      >
        Cancel
      </button>
      <button
        onClick={() => void save()}
        className="rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-white transition-colors hover:bg-black"
      >
        Save
      </button>
    </footer>
  )
}
