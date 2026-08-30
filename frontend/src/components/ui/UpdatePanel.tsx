import { useEffect } from 'react'
import { Download, X, Clock, Package, ExternalLink } from 'lucide-react'
import { useUpdateStore } from '../../stores/updateStore'

export function UpdatePanel() {
  const { panelOpen, updateAvailable, updateInfo, checking, downloading, downloadProgress, closePanel, checkForUpdates, downloadUpdate, dismissUpdate } = useUpdateStore()

  // Auto-check on mount
  useEffect(() => {
    const lastChecked = useUpdateStore.getState().lastChecked
    // Check at most once per hour
    if (!lastChecked || Date.now() - lastChecked > 3_600_000) {
      checkForUpdates()
    }
  }, [])

  if (!panelOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={closePanel} />

      <div className="relative w-full max-w-md bg-surface border border-border rounded-xl shadow-2xl overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Package size={16} className="text-accent" />
            <span className="text-sm font-semibold text-text">
              {updateAvailable ? 'Update Available' : 'Check for Updates'}
            </span>
          </div>
          <button onClick={closePanel} className="p-1 text-text-muted hover:text-text rounded transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4">
          {checking ? (
            <div className="text-center py-6">
              <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-xs text-text-muted">Checking for updates...</p>
            </div>
          ) : updateAvailable && updateInfo ? (
            <div className="space-y-3">
              {/* Version info */}
              <div className="flex items-center justify-between bg-elevated border border-border rounded-lg px-3 py-2">
                <div>
                  <div className="text-xs text-text-muted">Current version</div>
                  <div className="text-sm text-text font-mono">{updateInfo.currentVersion}</div>
                </div>
                <div className="text-accent text-lg">→</div>
                <div className="text-right">
                  <div className="text-xs text-text-muted">Latest version</div>
                  <div className="text-sm text-accent font-mono font-semibold">{updateInfo.version}</div>
                </div>
              </div>

              {/* Release date & size */}
              <div className="flex items-center gap-3 text-[10px] text-text-muted">
                {updateInfo.releaseDate && (
                  <span className="flex items-center gap-1"><Clock size={10} /> {updateInfo.releaseDate}</span>
                )}
                {updateInfo.size && <span>{updateInfo.size}</span>}
              </div>

              {/* Changelog */}
              <div className="bg-bg border border-border rounded-lg overflow-hidden">
                <div className="px-3 py-1.5 bg-elevated text-[9px] text-text-muted uppercase">Changelog</div>
                <div className="px-3 py-2 text-[10px] text-text-sec whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {updateInfo.changelog}
                </div>
              </div>

              {/* Download progress */}
              {downloading && (
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[10px] text-text-muted">
                    <span>Downloading...</span>
                    <span>{Math.round(downloadProgress)}%</span>
                  </div>
                  <div className="h-2 bg-bg rounded-full overflow-hidden">
                    <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${downloadProgress}%` }} />
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-6">
              <div className="w-12 h-12 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-3">
                <Package size={20} className="text-green-400" />
              </div>
              <p className="text-sm text-text">You're up to date!</p>
              <p className="text-[11px] text-text-muted mt-1">Version {useUpdateStore.getState().currentVersion}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-border flex gap-2">
          {updateAvailable ? (
            <>
              <button onClick={dismissUpdate}
                className="flex-1 px-3 py-2 bg-elevated border border-border rounded-lg text-xs text-text-sec hover:border-accent/30 transition-colors">
                Skip This Version
              </button>
              <button onClick={downloadUpdate} disabled={downloading}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-accent text-onAccent rounded-lg text-xs font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors">
                {downloading ? (
                  <>Downloading...</>
                ) : (
                  <><Download size={12} /> Download Update</>
                )}
              </button>
            </>
          ) : (
            <>
              <button onClick={checkForUpdates} disabled={checking}
                className="flex-1 px-3 py-2 bg-elevated border border-border rounded-lg text-xs text-text-sec hover:border-accent/30 transition-colors">
                Check Again
              </button>
              <a href="https://github.com/nicepkg/gguf-loader/releases" target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 px-3 py-2 bg-elevated border border-border rounded-lg text-xs text-text-sec hover:border-accent/30 transition-colors">
                <ExternalLink size={11} /> All Releases
              </a>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
