import { create } from 'zustand'
import { notify } from './notificationStore'

interface QueuedMessage {
  id: string
  text: string
  timestamp: number
  type: 'chat' | 'agent'
}

interface OfflineState {
  isOnline: boolean
  wasOffline: boolean
  queuedMessages: QueuedMessage[]
  lastOnline: number | null
  lastOffline: number | null
  syncing: boolean
  retryCount: number

  // Actions
  sendMessage: (text: string, type?: 'chat' | 'agent') => void
  syncQueued: () => Promise<void>
  clearQueue: () => void
  getQueueSize: () => number
}

let offlineCounter = 0

export const useOfflineStore = create<OfflineState>((set, get) => ({
  isOnline: navigator.onLine,
  wasOffline: false,
  queuedMessages: [],
  lastOnline: navigator.onLine ? Date.now() : null,
  lastOffline: null,
  syncing: false,
  retryCount: 0,

  sendMessage: (text, type = 'chat') => {
    const { isOnline } = get()
    if (isOnline) {
      // Send directly — don't queue
      return
    }

    // Queue for later
    const msg: QueuedMessage = {
      id: `offline_${++offlineCounter}_${Date.now()}`,
      text,
      timestamp: Date.now(),
      type,
    }

    set((s) => ({
      queuedMessages: [...s.queuedMessages, msg],
    }))

    notify.info('Message Queued', `"${text.slice(0, 40)}..." will be sent when online`)

    // Persist queue
    try {
      localStorage.setItem('ggufloader_offline_queue', JSON.stringify(get().queuedMessages))
    } catch {}
  },

  syncQueued: async () => {
    const { queuedMessages } = get()
    if (queuedMessages.length === 0) return

    set({ syncing: true })

    let sent = 0
    let failed = 0

    for (const msg of queuedMessages) {
      try {
        // Try to send via WebSocket or REST
        const res = await fetch('/api/chat/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg.text }),
          signal: AbortSignal.timeout(10000),
        })
        if (res.ok) {
          sent++
        } else {
          failed++
        }
      } catch {
        failed++
        break // If one fails, stop trying
      }
    }

    // Remove sent messages from queue
    if (sent > 0) {
      set((s) => ({
        queuedMessages: s.queuedMessages.slice(sent),
      }))
      notify.success('Sync Complete', `${sent} queued message${sent !== 1 ? 's' : ''} sent`)
    }

    if (failed > 0 && sent === 0) {
      set((s) => ({ retryCount: s.retryCount + 1 }))
      notify.warning('Sync Failed', `${failed} message${failed !== 1 ? 's' : ''} could not be sent`)
    }

    set({ syncing: false })

    // Persist updated queue
    try {
      localStorage.setItem('ggufloader_offline_queue', JSON.stringify(get().queuedMessages))
    } catch {}
  },

  clearQueue: () => {
    set({ queuedMessages: [], retryCount: 0 })
    try { localStorage.removeItem('ggufloader_offline_queue') } catch {}
  },

  getQueueSize: () => get().queuedMessages.length,
}))

// Initialize connectivity listeners
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    const store = useOfflineStore.getState()
    const wasOffline = !store.isOnline
    useOfflineStore.setState({
      isOnline: true,
      wasOffline,
      lastOnline: Date.now(),
    })

    if (wasOffline) {
      notify.success('Back Online', 'Connection restored')
      // Auto-sync queued messages
      setTimeout(() => {
        useOfflineStore.getState().syncQueued()
      }, 1000)
    }
  })

  window.addEventListener('offline', () => {
    useOfflineStore.setState({
      isOnline: false,
      lastOffline: Date.now(),
    })
    notify.warning('Offline', 'You are currently offline. Messages will be queued.')
  })

  // Restore queue from localStorage
  try {
    const saved = localStorage.getItem('ggufloader_offline_queue')
    if (saved) {
      useOfflineStore.setState({ queuedMessages: JSON.parse(saved) })
    }
  } catch {}
}
