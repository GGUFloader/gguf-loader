import { create } from 'zustand'
import { modelApi } from '../api/client'
import { useModelStore } from './modelStore'

export interface DownloadStatus {
  status: string // idle | downloading | done | error | disabled
  progress: number // 0..1
  message?: string | null
  path?: string | null
}

interface DownloadState {
  dl: DownloadStatus | null
  startDownload: () => Promise<void>
  stopPolling: () => void
  reset: () => void
}

let timer: ReturnType<typeof setTimeout> | null = null

/**
 * Owns the pinned-model download lifecycle so any component (header chip,
 * model picker, compatibility dialog) can render live progress. Polling
 * keeps running until the download reaches a terminal state, even when the
 * picker that started it is closed.
 */
export const useDownloadStore = create<DownloadState>((set) => ({
  dl: null,

  startDownload: async () => {
    if (timer) { clearTimeout(timer); timer = null }
    set({ dl: { status: 'downloading', progress: 0 } })
    try {
      await modelApi.downloadPinned()
      const tick = async () => {
        try {
          const s = await modelApi.downloadStatus()
          set({
            dl: {
              status: s.status,
              progress: s.progress || 0,
              message: s.message,
              path: s.path,
            },
          })
          if (s.status === 'downloading') {
            timer = setTimeout(tick, 1000)
          } else {
            if (s.status === 'done') {
              // Auto-load runs server-side in the background; refresh a
              // couple of times so the header chip picks up the loaded model.
              useModelStore.getState().refreshInfo()
              timer = setTimeout(() => useModelStore.getState().refreshInfo(), 5000)
            } else {
              timer = null
            }
          }
        } catch {
          set({ dl: { status: 'error', progress: 0, message: 'Could not reach the model service' } })
          timer = null
        }
      }
      tick()
    } catch (e: any) {
      set({ dl: { status: 'error', progress: 0, message: e.message || 'Download failed' } })
      timer = null
    }
  },

  stopPolling: () => {
    if (timer) { clearTimeout(timer); timer = null }
  },

  reset: () => {
    if (timer) { clearTimeout(timer); timer = null }
    set({ dl: null })
  },
}))