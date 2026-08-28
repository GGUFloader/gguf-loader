import { useState, useEffect } from 'react'
import { Puzzle, RefreshCw, ToggleLeft, ToggleRight } from 'lucide-react'
import { pluginsApi } from '../../api/client'

interface Plugin {
  name: string
  status: string
  enabled: boolean
}

export function PluginPanel() {
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadPlugins() }, [])

  async function loadPlugins() {
    setLoading(true)
    try {
      const [p, s] = await Promise.all([pluginsApi.list(), pluginsApi.stats()])
      setPlugins(p)
      setStats(s)
    } catch {}
    setLoading(false)
  }

  async function handleToggle(name: string, enabled: boolean) {
    if (enabled) {
      await pluginsApi.enable(name)
    } else {
      await pluginsApi.disable(name)
    }
    loadPlugins()
  }

  return (
    <div className="h-full flex flex-col p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Puzzle size={14} className="text-accent" />
          Plugins
        </h3>
        <button onClick={loadPlugins} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {stats && (
        <div className="flex gap-3 text-[10px] text-text-muted">
          <span>{stats.total} installed</span>
          <span>{stats.loaded} loaded</span>
          <span>{stats.failed} failed</span>
        </div>
      )}

      {loading ? (
        <div className="text-xs text-text-muted">Loading...</div>
      ) : plugins.length === 0 ? (
        <div className="center py-8 text-text-muted text-xs">
          <Puzzle size={24} className="mx-auto mb-2 opacity-30" />
          <p>No plugins installed</p>
          <p className="mt-1 text-text-muted/50">Add plugins to .ggufloader/plugins/ to extend functionality</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-2">
          {plugins.map(p => (
            <div key={p.name} className="bg-elevated border border-border rounded-lg p-3 flex items-center justify-between">
              <div className="min-w-0">
                <div className="text-xs font-medium text-text">{p.name}</div>
                <div className="text-[10px] text-text-muted">{p.status}</div>
              </div>
              <button onClick={() => handleToggle(p.name, !p.enabled)} className="transition-colors">
                {p.enabled ? (
                  <ToggleRight size={20} className="text-accent" />
                ) : (
                  <ToggleLeft size={20} className="text-text-muted" />
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
