import { create } from 'zustand'
import type { ModelInfo } from '../api/types'
import { modelApi } from '../api/client'

interface ModelState {
  info: ModelInfo
  loading: boolean
  error: string | null
  loadModel: (path: string, useGpu?: boolean | null, nCtx?: number | null, nGpuLayers?: number | null) => Promise<void>
  unloadModel: () => Promise<void>
  refreshInfo: () => Promise<void>
}

let _refreshTimer: ReturnType<typeof setInterval> | null = null

/**
 * Poll /model/info after app boot until the startup auto-load finishes,
 * so the header chip reflects the model the backend loaded without any
 * user action. Stops once a model is loaded (or after ~90 s when none
 * exists — e.g. the download prompt takes over from there).
 */
export function startModelRefresh() {
  useModelStore.getState().refreshInfo()
  if (_refreshTimer) clearInterval(_refreshTimer)
  _refreshTimer = null
  let tries = 0
  _refreshTimer = setInterval(async () => {
    tries += 1
    await useModelStore.getState().refreshInfo()
    if (useModelStore.getState().info.loaded || tries >= 30) {
      if (_refreshTimer) clearInterval(_refreshTimer)
      _refreshTimer = null
    }
  }, 3000)
}

export function stopModelRefresh() {
  if (_refreshTimer) {
    clearInterval(_refreshTimer)
    _refreshTimer = null
  }
}

export const useModelStore = create<ModelState>((set) => ({
  info: { loaded: false, gpu: false },
  loading: false,
  error: null,

  loadModel: async (path, useGpu = null, nCtx = null, nGpuLayers = null) => {
    set({ loading: true, error: null })
    try {
      await modelApi.load(path, useGpu, nCtx, nGpuLayers)
      const info = await modelApi.info()
      set({ info, loading: false })
    } catch (e: any) {
      set({ error: e.message, loading: false })
    }
  },

  unloadModel: async () => {
    try {
      await modelApi.unload()
      set({ info: { loaded: false, gpu: false } })
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  refreshInfo: async () => {
    try {
      const info = await modelApi.info()
      set({ info })
    } catch {}
  },
}))
