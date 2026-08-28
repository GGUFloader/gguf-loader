import { useState, useEffect } from 'react'
import { useModelStore } from '../../stores/modelStore'
import { useUIStore } from '../../stores/uiStore'
import { ModeSelector } from '../agent/ModeSelector'
import { modelApi, gpuApi } from '../../api/client'
import { PanelLeftClose, PanelRightClose, Cpu, X } from 'lucide-react'

export function Header() {
  const { info } = useModelStore()
  const { toggleLeftPanel, toggleRightPanel } = useUIStore()
  const [gpuOk, setGpuOk] = useState<boolean | null>(null)

  useEffect(() => {
    gpuApi.status().then(s => setGpuOk(s.gpu_available)).catch(() => setGpuOk(false))
  }, [])

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
        {/* GPU badge */}
        {gpuOk !== null && (
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-[10px] ${gpuOk ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-elevated text-text-muted border border-border'}`}>
            <Cpu size={10} />
            {gpuOk ? 'GPU Ready' : 'CPU Only'}
          </div>
        )}

        {/* Model chip */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-elevated rounded-full border border-border text-sm">
          <div className={`w-2 h-2 rounded-full ${info.loaded ? 'bg-success' : 'bg-text-muted'}`} />
          <span className="text-text-sec max-w-[200px] truncate">
            {info.loaded ? info.filename : 'No model loaded'}
          </span>
          {info.gpu && <Cpu size={14} className="text-accent" />}
          {info.loaded && (
            <button onClick={async () => { await modelApi.unload() }}
              className="p-0.5 text-text-muted hover:text-red-400 transition-colors" title="Unload model">
              <X size={12} />
            </button>
          )}
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
