import { useState, useEffect, useCallback } from 'react'
import {
  X, FolderOpen, Cpu, HardDrive, Loader2, CheckCircle2,
  AlertTriangle, Zap, Clock, Sparkles,
} from 'lucide-react'
import { modelApi } from '../../api/client'
import { toast } from '../../stores/toastStore'
import type { ModelInfo, MemoryEstimate } from '../../api/types'

interface Props {
  onClose: () => void
  onLoaded?: (info: ModelInfo) => void
}

const RECENT_MODELS_KEY = 'ggufloader_recent_models'

export function ModelLoadDialog({ onClose, onLoaded }: Props) {
  const [modelPath, setModelPath] = useState('')
  const [useGpu, setUseGpu] = useState(true)
  const [gpuLayers, setGpuLayers] = useState(-1)
  const [ctxLength, setCtxLength] = useState(0) // 0 = Auto (router decides)
  const [plan, setPlan] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [estimating, setEstimating] = useState(false)
  const [estimate, setEstimate] = useState<MemoryEstimate | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [currentModel, setCurrentModel] = useState<ModelInfo | null>(null)
  const [recentModels, setRecentModels] = useState<string[]>([])
  const [compat, setCompat] = useState<{ ok: boolean; label?: string } | null>(null)
  const [compatLoading, setCompatLoading] = useState(false)

  // Load current model info + recent models
  useEffect(() => {
    modelApi.info().then(setCurrentModel).catch(() => {})
    try {
      const saved = localStorage.getItem(RECENT_MODELS_KEY)
      if (saved) setRecentModels(JSON.parse(saved))
    } catch {}
  }, [])

  // Pinned-target compatibility check (mirrors the backend load gate):
  // only Gemma 4 12B Q4_K_M passes.
  const fetchCompat = useCallback(async (path: string) => {
    if (!path || !path.endsWith('.gguf')) { setCompat(null); return }
    setCompatLoading(true)
    try {
      const p = await modelApi.inspect(path)
      const arch = (p.architecture || '').toLowerCase()
      const quantBlob = `${p.quantization || ''} ${p.filename || ''}`.toUpperCase()
      const sizeBlob = `${p.param_estimate || ''} ${p.filename || ''}`.toUpperCase()
      const ok = arch === 'gemma4' && quantBlob.includes('Q4_K_M') && sizeBlob.includes('12B')
      setCompat(ok
        ? { ok: true, label: p.filename || 'Gemma 4 12B Q4_K_M' }
        : { ok: false, label: `${p.architecture || 'unknown'} · ${p.quantization || 'unknown'} · ${p.param_estimate || 'unknown'}` })
    } catch { setCompat(null) }
    setCompatLoading(false)
  }, [])

  // Estimate memory when path changes
  const debounceEstimate = useCallback(async (path: string) => {
    if (!path || !path.endsWith('.gguf')) { setEstimate(null); return }
    setEstimating(true)
    try {
      const est = await modelApi.estimate(path)
      setEstimate(est)
    } catch { setEstimate(null) }
    setEstimating(false)
  }, [])

  // Router plan preview: shows recommended ctx / gpu layers + fit badges.
  // Switching to a custom ctx re-plans so the dialog shows whether it fits.
  useEffect(() => {
    if (!modelPath.trim() || !modelPath.endsWith('.gguf')) { setPlan(null); return }
    const id = setTimeout(async () => {
      try {
        setPlan(await modelApi.plan(modelPath, ctxLength === 0 ? null : ctxLength))
      } catch { setPlan(null) }
    }, 250)
    return () => clearTimeout(id)
  }, [modelPath, ctxLength])

  useEffect(() => {
    const timer = setTimeout(() => {
      debounceEstimate(modelPath)
      fetchCompat(modelPath)
    }, 500)
    return () => clearTimeout(timer)
  }, [modelPath, debounceEstimate, fetchCompat])

  function addToRecent(path: string) {
    const updated = [path, ...recentModels.filter(p => p !== path)].slice(0, 5)
    setRecentModels(updated)
    localStorage.setItem(RECENT_MODELS_KEY, JSON.stringify(updated))
  }

  async function handleLoad() {
    if (!modelPath.trim()) { setError('Please enter a model path'); return }
    setLoading(true); setError(null)
    try {
      if (currentModel?.loaded) await modelApi.unload()
      const nCtx = ctxLength === 0 ? null : ctxLength
      const nGpuLayers = (useGpu && gpuLayers >= 0) ? gpuLayers : (useGpu ? null : 0)
      const result = await modelApi.load(modelPath, useGpu, nCtx, nGpuLayers)
      addToRecent(modelPath)
      toast.success(`Model loaded: ${result.filename || modelPath.split(/[/\\\\]/).pop()}`)
      onLoaded?.(result)
      onClose()
    } catch (e: any) {
      setError(e.message || 'Failed to load model')
      toast.error(`Model load failed: ${e.message}`)
    }
    setLoading(false)
  }

  function handleBrowse() {
    if ((window as any).electronAPI?.openFileDialog) {
      (window as any).electronAPI.openFileDialog().then((path: string | null) => {
        if (path) setModelPath(path)
      })
    } else {
      const path = prompt('Enter the full path to a .gguf model file:')
      if (path) setModelPath(path)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-surface border border-border rounded-xl shadow-2xl w-[540px] max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <HardDrive size={18} className="text-accent" />
            <h2 className="text-base font-semibold text-text">Load Model</h2>
          </div>
          <button onClick={onClose} className="p-1.5 text-text-muted hover:text-text rounded-lg hover:bg-elevated transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* Current model */}
          {currentModel?.loaded && (
            <div className="flex items-center gap-2 px-3 py-2 bg-green-500/10 border border-green-500/20 rounded-lg">
              <CheckCircle2 size={14} className="text-green-400" />
              <span className="text-sm text-text">Currently: </span>
              <span className="text-sm text-green-400 font-medium truncate">{currentModel.filename}</span>
            </div>
          )}

          {/* Recent models */}
          {recentModels.length > 0 && !modelPath && (
            <div>
              <label className="text-xs text-text-muted mb-1.5 block">Recent Models</label>
              <div className="space-y-1">
                {recentModels.map((path) => (
                  <button key={path} onClick={() => setModelPath(path)}
                    className="w-full flex items-center gap-2 px-3 py-2 bg-elevated/50 border border-border rounded-lg text-xs text-left hover:border-accent transition-colors">
                    <Clock size={11} className="text-text-muted flex-shrink-0" />
                    <span className="truncate text-text-sec">{path.split(/[/\\\\]/).pop()}</span>
                    <span className="truncate text-text-muted ml-auto font-mono text-[10px]">{path}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Model path */}
          <div>
            <label className="text-sm text-text-sec mb-1.5 block">Model Path (.gguf)</label>
            <div className="flex gap-2">
              <input value={modelPath} onChange={(e) => { setModelPath(e.target.value); setError(null) }}
                placeholder="C:/models/llama-7b.gguf"
                className="flex-1 bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-text-muted outline-none focus:border-accent font-mono" />
              <button onClick={handleBrowse}
                className="px-3 py-2 bg-elevated border border-border rounded-lg text-sm text-text-sec hover:border-accent transition-colors">
                <FolderOpen size={16} />
              </button>
            </div>
          </div>

          {/* Memory estimate */}
          {(estimating || estimate) && (
            <div className="px-3 py-2 bg-elevated/50 rounded-lg">
              {estimating ? (
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <Loader2 size={12} className="animate-spin" /> Estimating memory...
                </div>
              ) : estimate ? (
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <div className="text-text-muted">RAM Needed</div>
                    <div className="text-text font-medium">{estimate.ram_gb?.toFixed(1) || '?'} GB</div>
                  </div>
                  <div>
                    <div className="text-text-muted">VRAM (GPU)</div>
                    <div className={`font-medium ${estimate.fits_in_vram ? 'text-green-400' : 'text-yellow-400'}`}>
                      {estimate.vram_gb?.toFixed(1) || '?'} GB
                    </div>
                  </div>
                  <div>
                    <div className="text-text-muted">Quantization</div>
                    <div className="text-text font-medium">{estimate.quantization || '?'}</div>
                  </div>
                </div>
              ) : null}
            </div>
          )}

          {/* Pinned-model compatibility verdict */}
          {(compatLoading || compat) && modelPath.endsWith('.gguf') && (
            <div className={`flex items-start gap-2 px-3 py-2 rounded-lg border ${
              compatLoading
                ? 'bg-elevated/50 border-border'
                : compat?.ok
                  ? 'bg-green-500/10 border-green-500/20'
                  : 'bg-amber-500/10 border-amber-500/20'
            }`}>
              {compatLoading ? (
                <Loader2 size={14} className="animate-spin text-text-muted mt-0.5 shrink-0" />
              ) : compat?.ok ? (
                <CheckCircle2 size={14} className="text-green-400 mt-0.5 shrink-0" />
              ) : (
                <AlertTriangle size={14} className="text-amber-400 mt-0.5 shrink-0" />
              )}
              <div className="text-xs leading-relaxed">
                {compatLoading ? (
                  <span className="text-text-muted">Checking compatibility...</span>
                ) : compat?.ok ? (
                  <span className="text-text">
                    <span className="text-green-400 font-medium">Compatible</span> —{' '}
                    <span className="font-mono">{compat.label}</span> matches the pinned Gemma 4 12B Q4_K_M target.
                  </span>
                ) : (
                  <span className="text-text">
                    <span className="text-amber-400 font-medium">Not the pinned model</span> —{' '}
                    <span className="font-mono">{compat?.label}</span>. This build only runs Gemma 4 12B Q4_K_M.
                  </span>
                )}
              </div>
            </div>
          )}

          {/* GPU toggle + layers */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu size={14} className="text-accent" />
                <span className="text-sm text-text">GPU Offload</span>
              </div>
              <button onClick={() => setUseGpu(!useGpu)}
                className={`relative w-9 h-5 rounded-full transition-colors ${useGpu ? 'bg-accent' : 'bg-border'}`}>
                <div className="absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform"
                  style={{ left: useGpu ? '18px' : '2px' }} />
              </button>
            </div>
            {useGpu && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-text-muted">GPU Layers</span>
                  <span className="text-xs text-accent font-mono">{gpuLayers === -1 ? 'Auto' : gpuLayers}</span>
                </div>
                <input type="range" min={-1} max={128} value={gpuLayers}
                  onChange={(e) => setGpuLayers(Number(e.target.value))}
                  className="w-full accent-accent" />
                <div className="flex justify-between text-[10px] text-text-muted">
                  <span>CPU only (0)</span>
                  <span>Auto (-1)</span>
                  <span>All (128)</span>
                </div>
              </div>
            )}
          </div>

          {/* Context length */}
          <div>
            <label className="text-sm text-text-sec mb-1.5 block">Context Length</label>
            <select value={ctxLength} onChange={(e) => setCtxLength(Number(e.target.value))}
              className="w-full bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-text outline-none focus:border-accent">
              <option value={0}>Auto (recommended)</option>
              {[2048,4096,8192,16384,32768,65536,131072].map(v => (
                <option key={v} value={v}>{v.toLocaleString()}</option>
              ))}
            </select>
          </div>

          {/* Router plan preview */}
          {plan && (
            <div className="px-4 py-2 bg-accent/5 border border-accent/20 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-accent flex items-center gap-1.5">
                  <Sparkles size={12} /> Router plan
                </span>
                <div className="flex items-center gap-2">
                  {plan.fits_vram
                    ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 text-green-400">VRAM ✓</span>
                    : <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/15 text-yellow-400">VRAM ✗</span>}
                  {plan.fits_ram
                    ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 text-green-400">RAM ✓</span>
                    : <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400">RAM ✗</span>}
                </div>
              </div>
              <div className="flex gap-3 text-[11px] font-mono text-text">
                <span>ctx {Number(plan.n_ctx).toLocaleString()}</span>
                <span>layers {plan.n_gpu_layers === -1 ? 'all' : plan.n_gpu_layers}</span>
                <span>batch {plan.batch_size}</span>
              </div>
              {plan.reasoning && (
                <div className="text-[11px] text-text-muted leading-snug">{plan.reasoning}</div>
              )}
            </div>
          )}

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
          <button onClick={onClose}
            className="px-4 py-2 text-sm text-text-sec hover:text-text rounded-lg hover:bg-elevated transition-colors">
            Cancel
          </button>
          <button onClick={handleLoad} disabled={!modelPath.trim() || loading}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-onAccent rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">
            {loading ? <><Loader2 size={14} className="animate-spin" /> Loading...</> : <><Zap size={14} /> Load Model</>}
          </button>
        </div>
      </div>
    </div>
  )
}
