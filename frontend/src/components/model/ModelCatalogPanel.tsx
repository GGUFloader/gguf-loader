import { useState, useEffect } from 'react'
import { FolderOpen, HardDrive, Brain, Search, RefreshCw, Download, ChevronRight, ChevronDown } from 'lucide-react'
import { modelApi } from '../../api/client'
import { useModelStore } from '../../stores/modelStore'

interface CatalogModel {
  path: string
  filename: string
  directory: string
  size_gb: number
  size_human: string
  family: string
  architecture: string
  size_tier: string
  context_length: number
  quantization: string
  metadata: Record<string, string>
}

const SIZE_TIER_COLORS: Record<string, string> = {
  tiny: 'text-green-400 bg-green-500/10 border-green-500/20',
  small: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  medium: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  large: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
  xlarge: 'text-red-400 bg-red-500/10 border-red-500/20',
  mega: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
}

export function ModelCatalogPanel() {
  const [models, setModels] = useState<CatalogModel[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [scanDir, setScanDir] = useState('')
  const [selectedModel, setSelectedModel] = useState<CatalogModel | null>(null)
  const [loadingModel, setLoadingModel] = useState(false)
  const [expandedMeta, setExpandedMeta] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<'filename' | 'size_gb' | 'family'>('filename')

  useEffect(() => { loadCatalog() }, [])

  async function loadCatalog(dir?: string) {
    setLoading(true)
    setError(null)
    try {
      const data = await modelApi.catalog(dir || undefined)
      setModels(data.models || [])
      if (data.directory) setScanDir(data.directory)
    } catch (e: any) {
      setError(e.message || 'Failed to load catalog')
    }
    setLoading(false)
  }

  async function handleLoadModel(m: CatalogModel) {
    setLoadingModel(true)
    try {
      await useModelStore.getState().loadModel(m.path)
    } catch {}
    setLoadingModel(false)
  }

  const filtered = models
    .filter(m => !search || m.filename.toLowerCase().includes(search.toLowerCase()) ||
      (m.family || '').toLowerCase().includes(search.toLowerCase()) ||
      (m.architecture || '').toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortBy === 'size_gb') return b.size_gb - a.size_gb
      if (sortBy === 'family') return (a.family || '').localeCompare(b.family || '')
      return a.filename.localeCompare(b.filename)
    })

  const families = [...new Set(models.map(m => m.family).filter(Boolean))]

  return (
    <div className="h-full flex flex-col p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Brain size={14} className="text-accent" />
          Model Catalog
        </h3>
        <button onClick={() => loadCatalog()} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Scan directory */}
      <div className="bg-elevated border border-border rounded-lg px-3 py-2">
        <div className="flex items-center gap-1.5 mb-1">
          <FolderOpen size={11} className="text-text-muted" />
          <span className="text-[10px] text-text-muted uppercase tracking-wider">Scanning</span>
        </div>
        <div className="text-[10px] text-text font-mono truncate">{scanDir || 'Default models directory'}</div>
        <div className="text-[9px] text-text-muted mt-0.5">{models.length} GGUF files found · {families.length} families</div>
      </div>

      {/* Search + sort */}
      <div className="flex gap-2">
        <div className="flex-1 flex items-center gap-2 px-2 py-1.5 bg-elevated border border-border rounded-lg">
          <Search size={14} className="text-text-muted" />
          <input
            type="text"
            placeholder="Filter models..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-transparent text-sm text-text placeholder-text-muted outline-none w-full"
          />
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as any)}
          className="bg-elevated border border-border rounded-lg px-2 py-1 text-[11px] text-text-sec outline-none"
        >
          <option value="filename">Name</option>
          <option value="size_gb">Size</option>
          <option value="family">Family</option>
        </select>
      </div>

      {loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Scanning for GGUF files...</div>
      ) : error ? (
        <div className="text-xs text-red-400 py-4 text-center">{error}</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-xs">
          <HardDrive size={24} className="mx-auto mb-2 opacity-30" />
          <p>No GGUF models found</p>
          <p className="mt-1 text-text-muted/50">Place .gguf files in the models directory</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-1.5">
          {filtered.map((m) => (
            <div
              key={m.path}
              className={`bg-elevated border rounded-lg transition-all ${
                selectedModel?.path === m.path ? 'border-accent/50 ring-1 ring-accent/20' : 'border-border hover:border-accent/30'
              }`}
            >
              <button
                onClick={() => setSelectedModel(selectedModel?.path === m.path ? null : m)}
                className="w-full text-left px-3 py-2"
              >
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium text-text truncate">{m.filename}</div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[9px] text-text-muted">{m.size_human}</span>
                      {m.family && <span className="text-[9px] text-accent">{m.family}</span>}
                      {m.quantization && <span className="text-[9px] text-text-muted">· {m.quantization}</span>}
                      {m.context_length > 0 && <span className="text-[9px] text-text-muted">· {m.context_length} ctx</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {m.size_tier && (
                      <span className={`text-[8px] px-1.5 py-0.5 rounded border ${SIZE_TIER_COLORS[m.size_tier] || 'text-text-muted bg-elevated border-border'}`}>
                        {m.size_tier}
                      </span>
                    )}
                    {selectedModel?.path === m.path ? <ChevronDown size={12} className="text-text-muted" /> : <ChevronRight size={12} className="text-text-muted" />}
                  </div>
                </div>
              </button>

              {/* Expanded detail */}
              {selectedModel?.path === m.path && (
                <div className="px-3 pb-2 space-y-2 border-t border-border/50">
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <div>
                      <span className="text-[9px] text-text-muted">Architecture</span>
                      <div className="text-[10px] text-text">{m.architecture || 'Unknown'}</div>
                    </div>
                    <div>
                      <span className="text-[9px] text-text-muted">Size</span>
                      <div className="text-[10px] text-text">{m.size_gb} GB</div>
                    </div>
                    <div>
                      <span className="text-[9px] text-text-muted">Context</span>
                      <div className="text-[10px] text-text">{m.context_length > 0 ? `${m.context_length} tokens` : 'Unknown'}</div>
                    </div>
                    <div>
                      <span className="text-[9px] text-text-muted">Path</span>
                      <div className="text-[9px] text-text font-mono truncate">{m.directory}</div>
                    </div>
                  </div>

                  {/* Router info */}
                  {m.family && (
                    <div className="bg-bg rounded-lg px-2 py-1.5">
                      <div className="text-[9px] text-accent font-medium mb-1">Router Profile</div>
                      <div className="text-[9px] text-text-sec">
                        Family: {m.family} · Tier: {m.size_tier || 'auto'} · {m.context_length > 0 ? `Max ctx: ${m.context_length}` : 'Default ctx'}
                      </div>
                    </div>
                  )}

                  {/* Metadata toggle */}
                  {Object.keys(m.metadata).length > 0 && (
                    <div>
                      <button
                        onClick={(e) => { e.stopPropagation(); setExpandedMeta(expandedMeta === m.path ? null : m.path) }}
                        className="text-[9px] text-text-muted hover:text-text transition-colors"
                      >
                        {expandedMeta === m.path ? 'Hide metadata' : 'Show metadata'}
                      </button>
                      {expandedMeta === m.path && (
                        <div className="mt-1 bg-bg rounded-lg px-2 py-1.5 max-h-32 overflow-y-auto">
                          {Object.entries(m.metadata).map(([k, v]) => (
                            <div key={k} className="text-[8px] text-text-sec flex gap-1">
                              <span className="text-text-muted flex-shrink-0">{k}:</span>
                              <span className="truncate">{v}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Load button */}
                  <button
                    onClick={(e) => { e.stopPropagation(); handleLoadModel(m) }}
                    disabled={loadingModel}
                    className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-accent text-onAccent rounded-lg text-[11px] font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors"
                  >
                    <Download size={12} />
                    {loadingModel ? 'Loading...' : 'Load Model'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
