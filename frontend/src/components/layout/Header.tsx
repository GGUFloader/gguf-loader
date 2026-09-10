import { useState, useEffect } from 'react'
import { useModelStore } from '../../stores/modelStore'
import { useDownloadStore } from '../../stores/downloadStore'
import { useUIStore } from '../../stores/uiStore'
import { modelApi, gpuApi } from '../../api/client'
import { PanelLeftClose, PanelRightClose, Cpu, X, Download } from 'lucide-react'
import { NotificationBell } from '../ui/NotificationPanel'
import { useUpdateStore } from '../../stores/updateStore'

export function Header() {
  const { info } = useModelStore()
  const dl = useDownloadStore((s) => s.dl)
  const { toggleLeftPanel, toggleRightPanel } = useUIStore()
  const [gpuOk, setGpuOk] = useState<boolean | null>(null)

  useEffect(() => {
    gpuApi.status().then(s => setGpuOk(s.gpu_available)).catch(() => setGpuOk(false))
  }, [])

  // Once the downloaded model is actually loaded, retire the download
  // indicator so a later unload shows the plain "No model" chip again.
  useEffect(() => {
    if (info.loaded && dl?.status === 'done') {
      useDownloadStore.getState().reset()
    }
  }, [info.loaded, dl?.status])

  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-border bg-surface">
      {/* Left: panel toggle + title */}
      <div className="flex items-center gap-3">
        <button onClick={toggleLeftPanel} className="p-1.5 hover:bg-elevated rounded-lg transition-colors">
          <PanelLeftClose size={16} className="text-text-sec" />
        </button>
        <div className="flex items-center gap-2">
          <Cpu size={18} className="text-accent" />
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
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 bg-elevated rounded-full border border-border text-xs ${dl?.status === 'downloading' ? 'border-accent/40' : ''}`}
          title={dl?.status === 'downloading'
            ? `Downloading Gemma 4 12B Q4_K_M — ${Math.round(dl.progress * 100)}%`
            : (dl?.status === 'error' ? `Download failed: ${dl.message || ''}` : undefined)}
        >
          {dl?.status === 'downloading' ? (
            <>
              <Download size={11} className="text-accent animate-pulse" />
              <span className="text-text-sec max-w-[150px] truncate">
                {Math.round(dl.progress * 100)}%
              </span>
            </>
          ) : dl?.status === 'done' ? (
            <>
              <Download size={11} className="text-success" />
              <span className="text-text-sec max-w-[150px] truncate">
                {info.loaded ? info.filename : 'Downloaded — loading...'}
              </span>
            </>
          ) : dl?.status === 'error' ? (
            <>
              <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
              <span className="text-red-400 max-w-[150px] truncate">Download failed</span>
            </>
          ) : (
            <>
              <div className={`w-1.5 h-1.5 rounded-full ${info.loaded ? 'bg-success' : 'bg-text-muted'}`} />
              <span className="text-text-sec max-w-[150px] truncate">
                {info.loaded ? info.filename : 'No model'}
              </span>
              {info.gpu && <Cpu size={12} className="text-accent" />}
            </>
          )}
          {info.loaded && dl?.status !== 'downloading' && dl?.status !== 'done' && (
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
