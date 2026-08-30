import { useState, useEffect } from 'react'
import { FolderOpen, Plus, Trash2, RefreshCw, Clock, MessageSquare, Puzzle, Copy } from 'lucide-react'
import { notify } from '../../stores/notificationStore'

interface Workspace {
  id: string
  name: string
  path: string
  created_at: number
  last_used: number
  is_active: boolean
  stats: { sessions: number; plugins: number; templates: number }
}

export function WorkspaceManagerPanel() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')

  useEffect(() => { loadWorkspaces() }, [])

  async function loadWorkspaces() {
    setLoading(true)
    try {
      const res = await fetch('/api/workspaces')
      setWorkspaces(await res.json())
    } catch {}
    setLoading(false)
  }

  async function handleCreate() {
    if (!newName.trim()) return
    try {
      await fetch('/api/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName }),
      })
      setNewName('')
      setShowCreate(false)
      notify.success('Workspace Created', `"${newName}" is ready`)
      loadWorkspaces()
    } catch {}
  }

  async function handleSwitch(id: string) {
    try {
      await fetch(`/api/workspaces/${id}/switch`, { method: 'POST' })
      notify.info('Workspace Switched', 'Reload to apply changes')
      loadWorkspaces()
    } catch {}
  }

  async function handleRename(id: string) {
    if (!renameValue.trim()) return
    try {
      await fetch(`/api/workspaces/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: renameValue }),
      })
      setRenamingId(null)
      loadWorkspaces()
    } catch {}
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete workspace "${name}"?`)) return
    try {
      await fetch(`/api/workspaces/${id}`, { method: 'DELETE' })
      notify.info('Workspace Deleted', `"${name}" was removed`)
      loadWorkspaces()
    } catch {}
  }

  function formatDate(ts: number) {
    if (!ts) return ''
    const d = new Date(ts * 1000)
    const diff = Date.now() - d.getTime()
    if (diff < 86_400_000) return 'Today'
    if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)}d ago`
    return d.toLocaleDateString()
  }

  return (
    <div className="h-full flex flex-col p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <FolderOpen size={14} className="text-accent" />
          Workspaces
        </h3>
        <button onClick={loadWorkspaces} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Create new */}
      {showCreate ? (
        <div className="bg-elevated border border-border rounded-lg px-3 py-2 space-y-2">
          <input placeholder="Workspace name" value={newName} onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            className="w-full bg-bg border border-border rounded px-2 py-1.5 text-[11px] text-text outline-none focus:border-accent" autoFocus />
          <div className="flex gap-2">
            <button onClick={() => setShowCreate(false)} className="flex-1 px-2 py-1.5 bg-elevated border border-border rounded-lg text-[10px] text-text-sec hover:border-accent/30 transition-colors">Cancel</button>
            <button onClick={handleCreate} disabled={!newName.trim()}
              className="flex-1 px-2 py-1.5 bg-accent text-onAccent rounded-lg text-[10px] font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">Create</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setShowCreate(true)}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-accent/10 text-accent rounded-lg text-[11px] font-medium hover:bg-accent/20 transition-colors">
          <Plus size={12} /> New Workspace
        </button>
      )}

      {loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Loading workspaces...</div>
      ) : workspaces.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-xs">
          <FolderOpen size={24} className="mx-auto mb-2 opacity-30" />
          <p>No workspaces yet</p>
          <p className="mt-1 text-text-muted/50">Create one to organize your projects</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {workspaces.map(ws => (
            <div key={ws.id} className={`bg-elevated border rounded-lg transition-all ${ws.is_active ? 'border-accent/50 ring-1 ring-accent/20' : 'border-border hover:border-accent/30'}`}>
              <div className="px-3 py-2">
                <div className="flex items-center justify-between">
                  {renamingId === ws.id ? (
                    <div className="flex-1 flex items-center gap-1">
                      <input value={renameValue} onChange={e => setRenameValue(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleRename(ws.id)}
                        className="flex-1 bg-bg border border-accent rounded px-2 py-0.5 text-[11px] text-text outline-none" autoFocus />
                    </div>
                  ) : (
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-text">{ws.name}</span>
                        {ws.is_active && <span className="text-[8px] px-1.5 py-0.5 bg-accent/15 text-accent rounded">active</span>}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-[9px] text-text-muted">
                        <span className="flex items-center gap-0.5"><MessageSquare size={8} /> {ws.stats.sessions}</span>
                        <span className="flex items-center gap-0.5"><Puzzle size={8} /> {ws.stats.plugins}</span>
                        <span className="flex items-center gap-0.5"><Copy size={8} /> {ws.stats.templates}</span>
                        <span className="flex items-center gap-0.5"><Clock size={8} /> {formatDate(ws.last_used)}</span>
                      </div>
                    </div>
                  )}
                  <div className="flex items-center gap-1 ml-2">
                    {!ws.is_active && (
                      <button onClick={() => handleSwitch(ws.id)} className="px-2 py-0.5 bg-accent/10 text-accent rounded text-[9px] hover:bg-accent/20 transition-colors">Switch</button>
                    )}
                    <button onClick={() => { setRenamingId(ws.id); setRenameValue(ws.name) }} className="p-1 text-text-muted hover:text-text transition-colors text-[9px]">Rename</button>
                    <button onClick={() => handleDelete(ws.id, ws.name)} className="p-1 text-text-muted hover:text-red-400 transition-colors">
                      <Trash2 size={10} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
