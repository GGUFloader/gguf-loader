import { useState, useEffect } from 'react'
import { GitCompare, Search, RefreshCw, Plus, ArrowRight, Check, AlertTriangle } from 'lucide-react'
import { modelApi } from '../../api/client'

interface CatalogModel {
  path: string
  filename: string
  size_gb: number
  size_human: string
  family: string
  architecture: string
  size_tier: string
  context_length: number
  quantization: string
}

interface ModelProfile {
  path: string
  filename: string
  file_size_gb: number
  architecture: string
  family: string
  family_label: string
  size_tier: string
  param_estimate: string
  total_layers: number
  quantization: string
  quant_tier: string
  trained_context: number
  max_context: number
  supports_system_prompt: boolean
  supports_vision: boolean
  is_embedding_model: boolean
  is_thinking_model: boolean
  model_memory_gb: number
  kv_memory_gb: number
  total_memory_gb: number
  strategy: {
    n_ctx: number
    n_gpu_layers: number
    use_gpu: boolean
    batch_size: number
    fits_vram: boolean
    fits_ram: boolean
    reasoning: string
  }
}

interface ComparisonResult {
  models: ModelProfile[]
  comparison: {
    size_diff_gb: number
    memory_diff_gb: number
    same_family: boolean
    same_architecture: boolean
    smaller_model: string
    higher_context: string
  }
  system: { ram_gb: number; vram_gb: number }
}

const FIELD_LABELS: Record<string, string> = {
  architecture: 'Architecture',
  family_label: 'Family',
  size_tier: 'Size Tier',
  param_estimate: 'Parameters',
  total_layers: 'Layers',
  quantization: 'Quantization',
  quant_tier: 'Quant Quality',
  trained_context: 'Trained Context',
  model_memory_gb: 'Model Memory',
  kv_memory_gb: 'KV Cache Memory',
  total_memory_gb: 'Total Memory',
}

function formatValue(key: string, val: any): string {
  if (val === null || val === undefined || val === 0) return '—'
  if (key.includes('context')) return val.toLocaleString()
  if (key.includes('gb')) return `${val} GB`
  if (key === 'supports_system_prompt' || key === 'supports_vision' || key === 'is_thinking_model') return val ? '✓' : '✗'
  return String(val)
}

export function ModelComparePanel() {
  const [models, setModels] = useState<CatalogModel[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [_loading, setLoading] = useState(true)
  const [comparing, setComparing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => { loadCatalog() }, [])

  async function loadCatalog() {
    setLoading(true)
    try {
      const data = await modelApi.catalog()
      setModels(data.models || [])
    } catch {}
    setLoading(false)
  }

  async function handleCompare() {
    if (selected.length < 2) return
    setComparing(true)
    setError(null)
    try {
      const data = await modelApi.compare(selected.slice(0, 3))
      setResult(data)
    } catch (e: any) {
      setError(e.message || 'Comparison failed')
    }
    setComparing(false)
  }

  function toggleSelect(path: string) {
    setSelected(prev => {
      if (prev.includes(path)) return prev.filter(p => p !== path)
      if (prev.length >= 3) return prev
      return [...prev, path]
    })
  }

  const filtered = models.filter(m => !search || m.filename.toLowerCase().includes(search.toLowerCase()) || (m.family || '').toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="h-full flex flex-col p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <GitCompare size={14} className="text-accent" />
          Model Comparison
        </h3>
        <button onClick={loadCatalog} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Model selector */}
      <div className="bg-elevated border border-border rounded-lg px-3 py-2">
        <div className="text-[10px] text-text-muted uppercase mb-1.5">Select models to compare (2-3)</div>
        <div className="flex items-center gap-2 px-2 py-1 bg-bg border border-border rounded-lg mb-2">
          <Search size={14} className="text-text-muted" />
          <input
            type="text"
            placeholder="Search models..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-transparent text-sm text-text placeholder-text-muted outline-none w-full"
          />
        </div>
        <div className="max-h-40 overflow-y-auto space-y-1">
          {filtered.map(m => {
            const sel = selected.includes(m.path)
            return (
              <button
                key={m.path}
                onClick={() => toggleSelect(m.path)}
                className={`w-full text-left flex items-center gap-2 px-2 py-1.5 rounded-lg text-[10px] transition-colors ${
                  sel ? 'bg-accent/10 border border-accent/30 text-accent' : 'hover:bg-bg border border-transparent text-text-sec'
                }`}
              >
                {sel ? <Check size={11} className="text-accent flex-shrink-0" /> : <Plus size={11} className="text-text-muted flex-shrink-0" />}
                <span className="truncate flex-1">{m.filename}</span>
                <span className="text-text-muted">{m.size_human}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Compare button */}
      <button
        onClick={handleCompare}
        disabled={selected.length < 2 || comparing}
        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-accent text-onAccent rounded-lg text-[11px] font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors"
      >
        <GitCompare size={12} />
        {comparing ? 'Comparing...' : `Compare ${selected.length} Models`}
      </button>

      {/* Error */}
      {error && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2 text-[10px] text-red-400 flex items-center gap-2">
          <AlertTriangle size={12} /> {error}
        </div>
      )}

      {/* Comparison result */}
      {result && result.models.length >= 2 && (
        <div className="space-y-3">
          {/* Comparison summary */}
          {result.comparison && Object.keys(result.comparison).length > 0 && (
            <div className="bg-accent/5 border border-accent/20 rounded-lg px-3 py-2">
              <div className="text-[10px] text-accent font-medium mb-1">Summary</div>
              <div className="space-y-0.5 text-[9px] text-text-sec">
                {result.comparison.same_family && <div className="flex items-center gap-1"><Check size={9} className="text-green-400" /> Same family ({result.models[0].family_label})</div>}
                {!result.comparison.same_family && <div className="flex items-center gap-1"><ArrowRight size={9} className="text-text-muted" /> Different families</div>}
                {result.comparison.size_diff_gb !== 0 && (
                  <div>Size difference: {Math.abs(result.comparison.size_diff_gb)} GB ({result.comparison.smaller_model})</div>
                )}
                {result.comparison.memory_diff_gb !== 0 && (
                  <div>Memory difference: {Math.abs(result.comparison.memory_diff_gb)} GB</div>
                )}
                {result.comparison.higher_context && (
                  <div>Higher context: {result.comparison.higher_context.split(/[/\\]/).pop()}</div>
                )}
              </div>
            </div>
          )}

          {/* Side-by-side profiles */}
          <div className="bg-elevated border border-border rounded-lg overflow-hidden">
            {/* Header row */}
            <div className="grid border-b border-border" style={{ gridTemplateColumns: `180px repeat(${result.models.length}, 1fr)` }}>
              <div className="px-2 py-1.5 text-[9px] text-text-muted font-medium">Feature</div>
              {result.models.map((m, i) => (
                <div key={i} className="px-2 py-1.5 text-[10px] text-text font-medium border-l border-border truncate">
                  {m.filename}
                </div>
              ))}
            </div>

            {/* Data rows */}
            {Object.entries(FIELD_LABELS).map(([key, label]) => {
              const values = result.models.map(m => formatValue(key, (m as any)[key]))
              const allSame = values.every(v => v === values[0])
              return (
                <div key={key} className="grid border-b border-border/50 last:border-0" style={{ gridTemplateColumns: `180px repeat(${result.models.length}, 1fr)` }}>
                  <div className="px-2 py-1.5 text-[9px] text-text-muted">{label}</div>
                  {values.map((val, i) => (
                    <div key={i} className={`px-2 py-1.5 text-[10px] border-l border-border/50 ${allSame ? 'text-text-sec' : 'text-text font-medium'}`}>
                      {val}
                    </div>
                  ))}
                </div>
              )
            })}

            {/* Memory section */}
            <div className="grid border-t border-border bg-bg/50" style={{ gridTemplateColumns: `180px repeat(${result.models.length}, 1fr)` }}>
              <div className="px-2 py-1.5 text-[9px] text-text-muted font-medium">Fits in VRAM?</div>
              {result.models.map((m, i) => (
                <div key={i} className="px-2 py-1.5 text-[10px] border-l border-border/50">
                  {m.strategy?.fits_vram ? <span className="text-green-400">✓ Yes</span> : <span className="text-amber-400">✗ No (partial offload)</span>}
                </div>
              ))}
            </div>
            <div className="grid border-b border-border/50" style={{ gridTemplateColumns: `180px repeat(${result.models.length}, 1fr)` }}>
              <div className="px-2 py-1.5 text-[9px] text-text-muted font-medium">Fits in RAM?</div>
              {result.models.map((m, i) => (
                <div key={i} className="px-2 py-1.5 text-[10px] border-l border-border/50">
                  {m.strategy?.fits_ram ? <span className="text-green-400">✓ Yes</span> : <span className="text-red-400">✗ No</span>}
                </div>
              ))}
            </div>

            {/* GPU layers */}
            <div className="grid border-b border-border/50" style={{ gridTemplateColumns: `180px repeat(${result.models.length}, 1fr)` }}>
              <div className="px-2 py-1.5 text-[9px] text-text-muted font-medium">GPU Layers</div>
              {result.models.map((m, i) => (
                <div key={i} className="px-2 py-1.5 text-[10px] text-text-sec border-l border-border/50">
                  {m.strategy?.n_gpu_layers ?? '—'}
                </div>
              ))}
            </div>

            {/* Strategy reasoning */}
            <div className="grid" style={{ gridTemplateColumns: `180px repeat(${result.models.length}, 1fr)` }}>
              <div className="px-2 py-1.5 text-[9px] text-text-muted font-medium">Strategy</div>
              {result.models.map((m, i) => (
                <div key={i} className="px-2 py-1.5 text-[9px] text-text-sec border-l border-border/50">
                  {m.strategy?.reasoning || '—'}
                </div>
              ))}
            </div>
          </div>

          {/* System info */}
          <div className="text-[9px] text-text-muted text-center">
            System: {result.system.ram_gb} GB RAM · {result.system.vram_gb} GB VRAM
          </div>
        </div>
      )}
    </div>
  )
}
