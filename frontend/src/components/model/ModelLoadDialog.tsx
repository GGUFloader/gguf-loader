import { useState, useEffect, useCallback } from 'react'
import {
  X,
  FolderOpen,
  Cpu,
  HardDrive,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Zap,
} from 'lucide-react'
import { modelApi } from '../../api/client'
import { toast } from '../../stores/toastStore'
import type { ModelInfo } from '../../api/types'

interface Props {
  onClose: () => void
  onLoaded?: (info: ModelInfo) => void
}

export function ModelLoadDialog({ onClose, onLoaded }: Props) {
  const [modelPath, setModelPath] = useState('')
  const [useGpu, setUseGpu] = useState(true)
  const [gpuLayers, setGpuLayers] = useState(-1)
  const [ctxLength, setCtxLength] = useState(32768)
  const [loading, setLoading] = useState(false)
  const [estimating, setEstimating] = useState(false)
  const [estimate, setEstimate] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [currentModel, setCurrentModel] = useState<ModelInfo | null>(null)

  // Load current model info
  useEffect(() => {
    modelApi.info().then(setCurrentModel).catch(() => {})
  }, [])

  // Estimate memory when path changes
  const debounceEstimate = useCallback(async (path: string) => {
    if (!path || !path.endsWith('.gguf')) {
      setEstimate(null)
      return
    }
    setEstimating(true)
    try {
      const est = await modelApi.estimate(path)
      setEstimate(est)
    } catch {
      setEstimate(null)
    }
    setEstimating(false)
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => debounceEstimate(modelPath), 500)
    return () => clearTimeout(timer)
  }, [modelPath, debounceEstimate])

  async function handleLoad() {
    if (!modelPath.trim()) {
      setError('Please enter a model path')
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Unload current model first
      if (currentModel?.loaded) {
        await modelApi.unload()
      }

      const result = await modelApi.load(modelPath, useGpu, ctxLength)
      toast.success(`Model loaded: ${result.filename || modelPath.split(/[/\\]/).pop()}`)
      onLoaded?.(result)
      onClose()
    } catch (e: any) {
      setError(e.message || 'Failed to load model')
      toast.error(`Model load failed: ${e.message}`)
    }

    setLoading(false)
  }

  function handleBrowse() {
    // Use Electron dialog if available, otherwise prompt
    if ((window as any).electronAPI?.openFileDialog) {
      (window as any).electronAPI.openFileDialog().then((path: string | null) => {
        if (path) setModelPath(path)
      })
    } else {
      // Fallback: prompt for path
      const path = prompt('Enter the full path to a .gguf model file:')
      if (path) setModelPath(path)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface border border-border rounded-xl shadow-2xl w-[520px] max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <HardDrive size={18} className="text-accent" />
            <h2 className="text-base font-semibold text-text">Load Model</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text rounded-lg hover:bg-elevated transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* Current model */}
          {currentModel?.loaded && (
            <div className="flex items-center gap-2 px-3 py-2 bg-green-500/10 border border-green-500/20 rounded-lg">
              <CheckCircle2 size={14} className="text-green-400" />
              <span className="text-sm text-text">Currently loaded: </span>
              <span className="text-sm text-green-400 font-medium truncate">{currentModel.filename}</span>
            </div>
          )}

          {/* Model path */}
          <div>
            <label className="text-sm text-text-sec mb-1.5 block">Model Path (.gguf)</label>
            <div className="flex gap-2">
              <input
                value={modelPath}
                onChange={(e) => {
                  setModelPath(e.target.value)
                  setError(null)
                }}
                placeholder="C:/models/llama-7b.gguf"
                className="flex-1 bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-text-muted outline-none focus:border-accent font-mono"
              />
              <button
                onClick={handleBrowse}
                className="px-3 py-2 bg-elevated border border-border rounded-lg text-sm text-text-sec hover:border-accent transition-colors"
              >
                <FolderOpen size={16} />
              </button>
            </div>
          </div>

          {/* Memory estimate */}
          {(estimating || estimate) && (
            <div className="px-3 py-2 bg-elevated/50 rounded-lg">
              {estimating ? (
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <Loader2 size={12} className="animate-spin" />
                  Estimating memory...
                </div>
              ) : estimate ? (
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <div className="text-text-muted">RAM Needed</div>
                    <div className="text-text font-medium">{estimate.ram_gb?.toFixed(1) || '?'} GB</div>
                  </div>
                  <div>
                    <div className="text-text-muted">VRAM (GPU)</div>
                    <div className="text-text font-medium">{estimate.vram_gb?.toFixed(1) || '?'} GB</div>
                  </div>
                  <div>
                    <div className="text-text-muted">Quantization</div>
                    <div className="text-text font-medium">{estimate.quantization || '?'}</div>
                  </div>
                </div>
              ) : null}
            </div>
          )}

          {/* GPU toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu size={14} className="text-accent" />
              <span className="text-sm text-text">GPU Offload</span>
            </div>
            <button
              onClick={() => setUseGpu(!useGpu)}
              className={`relative w-9 h-5 rounded-full transition-colors ${
                useGpu ? 'bg-accent' : 'bg-border'
              }`}
            >
              <div
                className="absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform"
                style={{ left: useGpu ? '18px' : '2px' }}
              />
            </button>
          </div>

          {/* GPU layers */}
          {useGpu && (
            <div>
              <label className="text-sm text-text-sec mb-1.5 block">
                GPU Layers <span className="text-text-muted">(-1 = auto, 0 = CPU only)</span>
              </label>
              <input
                type="number"
                value={gpuLayers}
                onChange={(e) => setGpuLayers(Number(e.target.value))}
                className="w-full bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-text outline-none focus:border-accent"
              />
            </div>
          )}

          {/* Context length */}
          <div>
            <label className="text-sm text-text-sec mb-1.5 block">Context Length</label>
            <select
              value={ctxLength}
              onChange={(e) => setCtxLength(Number(e.target.value))}
              className="w-full bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-text outline-none focus:border-accent"
            >
              <option value={2048}>2,048</option>
              <option value={4096}>4,096</option>
              <option value={8192}>8,192</option>
              <option value={16384}>16,384</option>
              <option value={32768}>32,768</option>
              <option value={65536}>65,536</option>
              <option value={131072}>131,072</option>
            </select>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
              <AlertTriangle size={14} className="text-red-400 flex-shrink-0" />
              <span className="text-sm text-red-400">{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-sec hover:text-text rounded-lg hover:bg-elevated transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleLoad}
            disabled={!modelPath.trim() || loading}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-onAccent rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors"
          >
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Loading...
              </>
            ) : (
              <>
                <Zap size={14} />
                Load Model
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
