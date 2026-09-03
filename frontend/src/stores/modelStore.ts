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
