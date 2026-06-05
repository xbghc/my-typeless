import { useEffect } from 'react'
import { useStore } from './store'
import Sidebar from './components/Sidebar'
import Footer from './components/Footer'
import ProviderModal from './components/ProviderModal'
import General from './pages/General'
import Stt from './pages/Stt'
import Llm from './pages/Llm'
import Glossary from './pages/Glossary'
import History from './pages/History'

const PAGES = { general: General, stt: Stt, llm: Llm, glossary: Glossary, history: History }

export default function App(): JSX.Element {
  const page = useStore((s) => s.page)
  const modal = useStore((s) => s.modal)
  const init = useStore((s) => s.init)
  const setHotkey = useStore((s) => s.setHotkey)
  const setCapturing = useStore((s) => s.setCapturing)

  useEffect(() => {
    void init()
  }, [init])

  useEffect(() => {
    return window.api.onHotkeyCaptured((key) => {
      setCapturing(false)
      if (key) setHotkey(key)
    })
  }, [setHotkey, setCapturing])

  const Page = PAGES[page]

  return (
    <div className="flex h-screen w-screen bg-white font-display">
      <Sidebar />
      <main className="relative flex flex-1 flex-col overflow-hidden">
        <div key={page} className="page-fade flex h-full flex-col overflow-hidden">
          <Page />
        </div>
        <Footer />
      </main>
      {modal && <ProviderModal />}
    </div>
  )
}
