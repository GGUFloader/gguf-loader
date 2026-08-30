import { useState, useEffect } from 'react'
import { useModelStore } from '../../stores/modelStore'
import { useUIStore } from '../../stores/uiStore'
import { modelApi, gpuApi } from '../../api/client'
import { PanelLeftClose, PanelRightClose, Cpu, X, Download } from 'lucide-react'
import { NotificationBell } from '../ui/NotificationPanel'
import { useUpdateStore } from '../../stores/updateStore'

export function Header() {
  const { info } = useModelStore()
  const { toggleLeftPanel, toggleRightPanel } = useUIStore()
  const [gpuOk, setGpuOk] = useState<boolean | null>(null)

  useEffect(() => {
    gpuApi.status().then(s => setGpuOk(s.gpu_available)).catch(() => setGpuOk(false))
  }, [])

  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-border bg-surface">
      {/* Left: panel toggle + title */}
      <div className="flex items-center gap-3">
        <button onClick={toggleLeftPanel} className="p-1.5 hover:bg-elevated rounded-lg transition-colors">
          <PanelLeftClose size={16} className="text-text-sec" />
        </button>
        <div className="flex items-center gap-2">
          <span className="text-lg">🦜</span>
          <span className="text-sm font-medium text-text">GGUF Loader</span>
        </div>
      </div>

      {/* Right: status + panel toggle */}
      <div className="flex items-center gap-2">
        {/* Update indicator */}
        {useUpdateStore.getState().updateAvailable && (
          <button onClick={() => useUpdateStore.getState().togglePanel()}
            className="p-1.5 bg-accent/10 text-accent rounded-lg hover:bg-accent/20 transition-colors" title="Update available">
            <Download size={14} />
          </button>
        )}

        {/* Notifications */}
        <NotificationBell />

        {/* Model chip — compact */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-elevated rounded-full border border-border text-xs">
          <div className={`w-1.5 h-1.5 rounded-full ${info.loaded ? 'bg-success' : 'bg-text-muted'}`} />
          <span className="text-text-sec max-w-[150px] truncate">
            {info.loaded ? info.filename : 'No model'}
          </span>
          {info.gpu && <Cpu size={12} className="text-accent" />}
          {info.loaded && (
            <button onClick={async () => { await modelApi.unload() }}
              className="p-0.5 text-text-muted hover:text-red-400 transition-colors" title="Unload">
              <X size={10} />
            </button>
          )}
        </div>

        {/* GPU badge — only show if available */}
        {gpuOk && (
          <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] bg-green-500/10 text-green-400 border border-green-500/20">
            <Cpu size={8} />
            GPU
          </div>
        )}

        <button onClick={toggleRightPanel} className="p-1.5 hover:bg-elevated rounded-lg transition-colors">
          <PanelRightClose size={16} className="text-text-sec" />
        </button>
      </div>
    </header>
  )
}
