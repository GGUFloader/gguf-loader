import { useModelStore } from '../../stores/modelStore'
import { useUIStore } from '../../stores/uiStore'
import { ModeSelector } from '../agent/ModeSelector'
import { PanelLeftClose, PanelRightClose, Cpu } from 'lucide-react'

export function Header() {
  const { info } = useModelStore()
  const { toggleLeftPanel, toggleRightPanel } = useUIStore()

  return (
    <header className="h-14 flex items-center justify-between px-4 border-b border-border bg-surface">
      <div className="flex items-center gap-3">
        <button onClick={toggleLeftPanel} className="p-1.5 hover:bg-elevated rounded-lg transition-colors">
          <PanelLeftClose size={18} className="text-text-sec" />
        </button>
        <div className="flex items-center gap-2">
          <span className="text-xl">🦜</span>
          <div>
            <div className="text-sm font-semibold text-text">GGUF Loader</div>
            <div className="text-xs text-text-muted">Local LLM Runtime</div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Model chip */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-elevated rounded-full border border-border text-sm">
          <div className={`w-2 h-2 rounded-full ${info.loaded ? 'bg-success' : 'bg-text-muted'}`} />
          <span className="text-text-sec">
            {info.loaded ? info.filename : 'No model loaded'}
          </span>
          {info.gpu && <Cpu size={14} className="text-accent" />}
        </div>

        {/* Mode selector */}
        <ModeSelector />

        <button onClick={toggleRightPanel} className="p-1.5 hover:bg-elevated rounded-lg transition-colors">
          <PanelRightClose size={18} className="text-text-sec" />
        </button>
      </div>
    </header>
  )
}
