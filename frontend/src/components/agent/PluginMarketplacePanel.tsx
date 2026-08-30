import { useState, useEffect } from 'react'
import { Puzzle, Search, RefreshCw, Download, Check, ToggleRight, Tag, Package } from 'lucide-react'
import { pluginsApi } from '../../api/client'

interface PluginItem {
  id: string
  name: string
  description: string
  category: string
  icon: string
  author?: string
  version?: string
  tags?: string[]
  tool_count?: number
  installed: boolean
  enabled?: boolean
  status?: string
}

interface Category {
  name: string
  count: number
  icon: string
}

export function PluginMarketplacePanel() {
  const [catalog, setCatalog] = useState<PluginItem[]>([])
  const [installed, setInstalled] = useState<PluginItem[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'browse' | 'installed'>('browse')
  const [expandedPlugin, setExpandedPlugin] = useState<string | null>(null)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [cat, inst, cats] = await Promise.all([
        pluginsApi.catalog(),
        pluginsApi.list(),
        pluginsApi.categories(),
      ])
      setCatalog(cat)
      setInstalled(inst)
      setCategories(cats)
    } catch {}
    setLoading(false)
  }

  async function handleToggle(plugin: PluginItem) {
    if (plugin.installed) {
      await pluginsApi.disable(plugin.id)
    } else {
      await pluginsApi.enable(plugin.id)
    }
    loadData()
  }

  const filteredCatalog = catalog
    .filter(p => !activeCategory || p.category === activeCategory)
    .filter(p => !search || p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase()) ||
      (p.tags || []).some(t => t.toLowerCase().includes(search.toLowerCase())))

  const installedIds = new Set(installed.map(p => p.id))

  return (
    <div className="h-full flex flex-col p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Puzzle size={14} className="text-accent" />
          Plugin Marketplace
        </h3>
        <button onClick={loadData} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Tab toggle */}
      <div className="flex gap-1 bg-elevated rounded-lg p-0.5">
        <button
          onClick={() => setActiveTab('browse')}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'browse' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}
        >
          Browse ({catalog.length})
        </button>
        <button
          onClick={() => setActiveTab('installed')}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'installed' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}
        >
          Installed ({installed.length})
        </button>
      </div>

      {/* Search */}
      <div className="flex items-center gap-2 px-2 py-1.5 bg-elevated border border-border rounded-lg">
        <Search size={14} className="text-text-muted" />
        <input
          type="text"
          placeholder={activeTab === 'browse' ? 'Search plugins...' : 'Search installed...'}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-transparent text-sm text-text placeholder-text-muted outline-none w-full"
        />
      </div>

      {/* Categories (browse only) */}
      {activeTab === 'browse' && categories.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setActiveCategory(null)}
            className={`text-[10px] px-2 py-1 rounded-full border transition-colors ${
              !activeCategory ? 'bg-accent/15 text-accent border-accent/30' : 'text-text-muted border-border hover:border-accent/30'
            }`}
          >
            All
          </button>
          {categories.map(cat => (
            <button
              key={cat.name}
              onClick={() => setActiveCategory(activeCategory === cat.name ? null : cat.name)}
              className={`text-[10px] px-2 py-1 rounded-full border transition-colors flex items-center gap-1 ${
                activeCategory === cat.name ? 'bg-accent/15 text-accent border-accent/30' : 'text-text-muted border-border hover:border-accent/30'
              }`}
            >
              {cat.icon} {cat.name} ({cat.count})
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Loading plugins...</div>
      ) : activeTab === 'installed' && installed.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-xs">
          <Package size={24} className="mx-auto mb-2 opacity-30" />
          <p>No plugins installed</p>
          <p className="mt-1 text-text-muted/50">Browse the marketplace to add plugins</p>
        </div>
      ) : activeTab === 'browse' && filteredCatalog.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-xs">
          <Puzzle size={24} className="mx-auto mb-2 opacity-30" />
          <p>No plugins found</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-1.5">
          {(activeTab === 'browse' ? filteredCatalog : installed.filter(p => !search || p.name.toLowerCase().includes(search.toLowerCase()))).map((plugin) => (
            <div
              key={plugin.id}
              className={`bg-elevated border rounded-lg transition-all ${
                expandedPlugin === plugin.id ? 'border-accent/50' : 'border-border hover:border-accent/30'
              }`}
            >
              <button
                onClick={() => setExpandedPlugin(expandedPlugin === plugin.id ? null : plugin.id)}
                className="w-full text-left px-3 py-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span className="text-lg">{plugin.icon || '🔧'}</span>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-text truncate">{plugin.name}</div>
                      <div className="text-[9px] text-text-muted truncate">{plugin.description}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 ml-2">
                    {installedIds.has(plugin.id) && (
                      <Check size={12} className="text-green-400" />
                    )}
                    {plugin.tool_count && (
                      <span className="text-[8px] text-text-muted">{plugin.tool_count} tools</span>
                    )}
                  </div>
                </div>
              </button>

              {expandedPlugin === plugin.id && (
                <div className="px-3 pb-2 space-y-2 border-t border-border/50">
                  <div className="flex items-center gap-3 text-[9px] text-text-muted mt-2">
                    {plugin.author && <span>by {plugin.author}</span>}
                    {plugin.version && <span>v{plugin.version}</span>}
                    <span className="px-1.5 py-0.5 bg-elevated rounded">{plugin.category}</span>
                  </div>
                  {plugin.tags && plugin.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {plugin.tags.map(tag => (
                        <span key={tag} className="text-[8px] px-1.5 py-0.5 bg-bg rounded text-text-muted flex items-center gap-0.5">
                          <Tag size={7} /> {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="text-[10px] text-text-sec">{plugin.description}</div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleToggle(plugin) }}
                    className={`w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors ${
                      installedIds.has(plugin.id)
                        ? 'bg-elevated border border-border text-text-sec hover:border-red-500/30 hover:text-red-400'
                        : 'bg-accent text-onAccent hover:bg-accent-hover'
                    }`}
                  >
                    {installedIds.has(plugin.id) ? (
                      <><ToggleRight size={12} /> Installed — Click to Remove</>
                    ) : (
                      <><Download size={12} /> Install Plugin</>
                    )}
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
