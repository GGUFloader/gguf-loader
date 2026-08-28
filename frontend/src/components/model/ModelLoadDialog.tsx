import { useState, useEffect, useCallback } from 'react'
import {
  X, FolderOpen, Cpu, HardDrive, Loader2, CheckCircle2,
  AlertTriangle, Zap, Clock, Sparkles, Brain, Settings2,
} from 'lucide-react'
import { modelApi } from '../../api/client'
import { toast } from '../../stores/toastStore'
import type { ModelInfo, MemoryEstimate } from '../../api/types'

interface ModelProfile {
  family: string
  label: string
  detected_via: string
  params: {
    temperature?: number
    top_k?: number
    top_p?: number
    repeat_penalty?: number
    min_p?: number
    [key: string]: unknown
  }
  supports_system_prompt: boolean
  is_embedding_model: boolean
  meta?: {
    architecture?: string
    name?: string
    [key: string]: unknown
  }
}

interface Props {
  onClose: () => void
  onLoaded?: (info: ModelInfo) => void
}

const RECENT_MODELS_KEY = 'ggufloader_recent_models'

export function ModelLoadDialog({ onClose, onLoaded }: Props) {
  const [modelPath, setModelPath] = useState('')
  const [useGpu, setUseGpu] = useState(true)
  const [gpuLayers, setGpuLayers] = useState(-1)
  const [ctxLength, setCtxLength] = useState(32768)
  const [loading, setLoading] = useState(false)
  const [estimating, setEstimating] = useState(false)
  const [estimate, setEstimate] = useState<MemoryEstimate | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [currentModel, setCurrentModel] = useState<ModelInfo | null>(null)
  const [recentModels, setRecentModels] = useState<string[]>([])
  const [profile, setProfile] = useState<ModelProfile | null>(null)
  const [profileLoading, setProfileLoading] = useState(false)

  // Load current model info + recent models
  useEffect(() => {
    modelApi.info().then(setCurrentModel).catch(() => {})
    try {
      const saved = localStorage.getItem(RECENT_MODELS_KEY)
      if (saved) setRecentModels(JSON.parse(saved))
    } catch {}
  }, [])

  // Fetch model profile (family detection, auto-configured params)
  const fetchProfile = useCallback(async (path: string) => {
    if (!path || !path.endsWith('.gguf')) { setProfile(null); return }
    setProfileLoading(true)
    try {
      const p = await modelApi.profile(path)
      setProfile(p as ModelProfile)
    } catch { setProfile(null) }
    setProfileLoading(false)
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

  useEffect(() => {
    const timer = setTimeout(() => {
      debounceEstimate(modelPath)
      fetchProfile(modelPath)
    }, 500)
    return () => clearTimeout(timer)
  }, [modelPath, debounceEstimate, fetchProfile])

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
      const result = await modelApi.load(modelPath, useGpu, ctxLength)
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

  function formatParamName(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
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

          {/* Model Profile — detected family & auto-configured params */}
          {(profileLoading || profile) && modelPath.endsWith('.gguf') && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-accent" />
                <span className="text-sm font-medium text-text">Detected Profile</span>
                {profileLoading && <Loader2 size={12} className="animate-spin text-text-muted" />}
              </div>

              {profile && (
                <div className="bg-accent/5 border border-accent/20 rounded-lg p-3 space-y-2.5">
                  {/* Family badge */}
                  <div className="flex items-center gap-2">
                    <Brain size={13} className="text-accent" />
                    <span className="text-xs text-text-muted">Family:</span>
                    <span className="text-xs font-medium text-accent bg-accent/10 px-2 py-0.5 rounded-full">
                      {profile.label || profile.family}
                    </span>
                    <span className="text-[10px] text-text-muted">({profile.detected_via})</span>
                  </div>

                  {/* Model name from meta */}
                  {profile.meta?.name && (
                    <div className="text-xs text-text-sec">
                      {profile.meta.name}
                      {profile.meta.architecture && (
                        <span className="text-text-muted"> · {profile.meta.architecture}</span>
                      )}
                    </div>
                  )}

                  {/* Auto-configured parameters */}
                  {profile.params && Object.keys(profile.params).length > 0 && (
                    <div>
                      <div className="flex items-center gap-1.5 mb-1">
                        <Settings2 size={11} className="text-text-muted" />
                        <span className="text-[10px] text-text-muted uppercase tracking-wider">Auto-configured</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(profile.params).filter(([, v]) => v != null && v !== 0).map(([key, value]) => (
                          <span key={key} className="text-[11px] bg-elevated border border-border rounded px-2 py-0.5 font-mono">
                            <span className="text-text-muted">{formatParamName(key)}</span>
                            <span className="text-text ml-1">{String(value)}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* System prompt support */}
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-text-muted">System prompt:</span>
                    {profile.supports_system_prompt ? (
                      <span className="text-green-400">✓ Supported</span>
                    ) : (
                      <span className="text-yellow-400">✗ Not supported</span>
                    )}
                  </div>
                </div>
              )}
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
              {[2048,4096,8192,16384,32768,65536,131072].map(v => (
                <option key={v} value={v}>{v.toLocaleString()}</option>
              ))}
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
          <button onClick={onClose}
            className="px-4 py-2 text-sm text-text-sec hover:text-text rounded-lg hover:bg-elevated transition-colors">
            Cancel
          </button>
          <button onClick={handleLoad} disabled={!modelPath.trim() || loading}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-onAccent rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">
            {loading ? <><Loader2 size={14} className="animate-spin" /> Loading...</> : <><Zap size={14} /> Load Model{profile ? ` (${profile.label || profile.family})` : ''}</>}
          </button>
        </div>
      </div>
    </div>
  )
}
