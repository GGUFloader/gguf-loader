import { useState, useEffect } from 'react'
import { Wrench, Shield, ShieldAlert, ShieldCheck, RefreshCw } from 'lucide-react'
import { toolsApi } from '../../api/client'

interface ToolInfo {
  name: string
  description: string
  source: string
  enabled: boolean
  risk_level: string
}

const RISK_ICONS = {
  low: { icon: ShieldCheck, color: 'text-green-400', bg: 'bg-green-500/10' },
  medium: { icon: Shield, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  high: { icon: ShieldAlert, color: 'text-red-400', bg: 'bg-red-500/10' },
}

export function ToolBrowserPanel() {
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => { loadTools() }, [])

  async function loadTools() {
    setLoading(true)
    try {
      const [t, s] = await Promise.all([toolsApi.list(), toolsApi.stats()])
      setTools(t)
      setStats(s)
    } catch {}
    setLoading(false)
  }

  const filtered = filter === 'all' ? tools : tools.filter(t => t.risk_level === filter)

  return (
    <div className="h-full flex flex-col p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Wrench size={14} className="text-accent" />
          Agent Tools
        </h3>
        <button onClick={loadTools} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {stats && (
        <div className="flex gap-3 text-[10px] text-text-muted">
          <span>{stats.total_tools} total</span>
          <span>{stats.builtin_tools} built-in</span>
          <span>{stats.mcp_tools} MCP</span>
          <span>{stats.plugin_tools} plugin</span>
        </div>
      )}

      <div className="flex gap-1">
        {['all', 'low', 'medium', 'high'].map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-2 py-0.5 rounded text-[10px] capitalize transition-colors ${filter === f ? 'bg-accent/15 text-accent' : 'text-text-muted hover:bg-elevated'}`}>
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-xs text-text-muted">Loading...</div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-1">
          {filtered.map(tool => {
            const risk = RISK_ICONS[tool.risk_level as keyof typeof RISK_ICONS] || RISK_ICONS.medium
            const RiskIcon = risk.icon
            return (
              <div key={tool.name} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-elevated/50 group">
                <RiskIcon size={12} className={risk.color} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-text font-mono">{tool.name}</div>
                  <div className="text-[10px] text-text-muted truncate">{tool.description}</div>
                </div>
                <span className="text-[9px] text-text-muted/50 px-1 py-0.5 rounded bg-bg/50">{tool.source}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
