import { Wifi, WifiOff, RefreshCw } from 'lucide-react'
import { useOfflineStore } from '../../stores/offlineStore'

export function OfflineIndicator() {
  const { isOnline, queuedMessages, syncing, syncQueued, clearQueue } = useOfflineStore()
  const queueSize = queuedMessages.length

  if (isOnline && queueSize === 0) return null

  return (
    <div className={`fixed top-14 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2 rounded-full shadow-lg text-xs font-medium transition-all ${
      isOnline
        ? 'bg-accent/20 text-accent border border-accent/30'
        : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
    }`} role="status" aria-live="polite">
      {isOnline ? (
        <>
          <Wifi size={14} />
          <span>Back online</span>
          {syncing && <RefreshCw size={12} className="animate-spin" />}
        </>
      ) : (
        <>
          <WifiOff size={14} />
          <span>Offline</span>
          {queueSize > 0 && (
            <span className="px-1.5 py-0.5 bg-amber-500/20 rounded-full text-[10px]">
              {queueSize} queued
            </span>
          )}
        </>
      )}

      {/* Actions */}
      {queueSize > 0 && !syncing && (
        <div className="flex items-center gap-1 ml-1">
          {isOnline && (
            <button onClick={syncQueued}
              className="px-2 py-0.5 bg-accent/20 text-accent rounded-full text-[10px] hover:bg-accent/30 transition-colors">
              Sync Now
            </button>
          )}
          <button onClick={clearQueue}
            className="px-2 py-0.5 text-text-muted hover:text-text rounded-full text-[10px] transition-colors">
            Clear
          </button>
        </div>
      )}
    </div>
  )
}
