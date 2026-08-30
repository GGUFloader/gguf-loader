import { useState, useEffect } from 'react'
import { LayoutDashboard, Puzzle, Brain, MessageSquare, Cpu, RefreshCw, HardDrive, Database } from 'lucide-react'
import { chatApi } from '../../api/client'

interface DashboardData {
  workspace: string
  plugins: { name: string; status: string }[]
  memory: { entries: any[]; count: number }
  sessions: { id: string; title: string; messages: number; updated: string }[]
  model: { loaded: boolean; path: string | null; filename: string | null } | null
  ram_gb: number
}

export function WorkspaceDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { loadDashboard() }, [])

  async function loadDashboard() {
    setLoading(true)
    setError(null)
    try {
      const d = await chatApi.dashboard()
      setData(d)
    } catch (e: any) {
      setError(e.message || 'Failed to load dashboard')
    }
    setLoading(false)
  }

  if (loading) {
    return (
      <div className="h-full flex flex-col p-4 space-y-3">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <LayoutDashboard size={14} className="text-accent" />
          Dashboard
        </h3>
        <div className="text-xs text-text-muted py-8 text-center">Loading workspace data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-full flex flex-col p-4 space-y-3">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <LayoutDashboard size={14} className="text-accent" />
          Dashboard
        </h3>
        <div className="text-xs text-red-400 py-4 text-center">{error}</div>
        <button onClick={loadDashboard} className="text-xs text-accent hover:text-accent-hover text-center">Retry</button>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col p-4 space-y-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <LayoutDashboard size={14} className="text-accent" />
          Dashboard
        </h3>
        <button onClick={loadDashboard} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Workspace path */}
      <div className="bg-elevated border border-border rounded-lg px-3 py-2">
        <div className="text-[10px] text-text-muted uppercase tracking-wider mb-0.5">Workspace</div>
        <div className="text-xs text-text font-mono truncate">{data?.workspace || '.'}</div>
      </div>

      {/* Model status */}
      <div className="bg-elevated border border-border rounded-lg px-3 py-2">
        <div className="flex items-center gap-2 mb-1">
          <Cpu size={12} className="text-accent" />
          <span className="text-[10px] text-text-muted uppercase tracking-wider">Model</span>
        </div>
        {data?.model?.loaded ? (
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-success" />
            <span className="text-xs text-text truncate">{data.model.filename}</span>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-text-muted" />
            <span className="text-xs text-text-muted">No model loaded</span>
          </div>
        )}
      </div>

      {/* Quick stats row */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-elevated border border-border rounded-lg px-2 py-2 text-center">
          <div className="text-lg font-semibold text-text">{data?.plugins?.length || 0}</div>
          <div className="text-[9px] text-text-muted uppercase">Plugins</div>
        </div>
        <div className="bg-elevated border border-border rounded-lg px-2 py-2 text-center">
          <div className="text-lg font-semibold text-text">{data?.memory?.count || 0}</div>
          <div className="text-[9px] text-text-muted uppercase">Memory</div>
        </div>
        <div className="bg-elevated border border-border rounded-lg px-2 py-2 text-center">
          <div className="text-lg font-semibold text-text">{data?.sessions?.length || 0}</div>
          <div className="text-[9px] text-text-muted uppercase">Sessions</div>
        </div>
      </div>

      {/* Plugins */}
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <Puzzle size={12} className="text-accent" />
          <span className="text-[10px] text-text-muted uppercase tracking-wider font-medium">Plugins</span>
        </div>
        {data?.plugins?.length ? (
          <div className="space-y-1">
            {data.plugins.map(p => (
              <div key={p.name} className="flex items-center gap-2 bg-elevated border border-border rounded-lg px-3 py-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-success" />
                <span className="text-xs text-text flex-1 truncate">{p.name}</span>
                <span className="text-[9px] text-text-muted">{p.status}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-[10px] text-text-muted/50 italic">No plugins installed</div>
        )}
      </div>

      {/* Memory entries */}
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <Brain size={12} className="text-purple-400" />
          <span className="text-[10px] text-text-muted uppercase tracking-wider font-medium">Memory</span>
        </div>
        {data?.memory?.entries?.length ? (
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {data.memory.entries.slice(0, 10).map((entry: any, i: number) => (
              <div key={i} className="bg-elevated border border-border rounded-lg px-3 py-1.5">
                <div className="text-[10px] text-text truncate">{typeof entry === 'string' ? entry : entry.content || entry.text || JSON.stringify(entry).slice(0, 100)}</div>
              </div>
            ))}
            {data.memory.count > 10 && (
              <div className="text-[9px] text-text-muted text-center">+ {data.memory.count - 10} more entries</div>
            )}
          </div>
        ) : (
          <div className="text-[10px] text-text-muted/50 italic">No memory entries yet</div>
        )}
      </div>

      {/* Recent sessions */}
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <MessageSquare size={12} className="text-blue-400" />
          <span className="text-[10px] text-text-muted uppercase tracking-wider font-medium">Recent Sessions</span>
        </div>
        {data?.sessions?.length ? (
          <div className="space-y-1">
            {data.sessions.slice(0, 5).map(s => (
              <div key={s.id} className="bg-elevated border border-border rounded-lg px-3 py-1.5 flex items-center justify-between">
                <div className="min-w-0">
                  <div className="text-xs text-text truncate">{s.title || 'Untitled'}</div>
                  <div className="text-[9px] text-text-muted">{s.messages} messages</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-[10px] text-text-muted/50 italic">No sessions yet</div>
        )}
      </div>

      {/* System resources */}
      <div className="bg-elevated border border-border rounded-lg px-3 py-2">
        <div className="flex items-center gap-2 mb-1">
          <HardDrive size={12} className="text-text-muted" />
          <span className="text-[10px] text-text-muted uppercase tracking-wider">System</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-text-sec">
          <span className="flex items-center gap-1"><Database size={10} /> {data?.ram_gb || '?'} GB RAM</span>
        </div>
      </div>
    </div>
  )
}
