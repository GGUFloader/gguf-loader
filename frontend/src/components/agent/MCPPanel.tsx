import { useState, useEffect } from 'react'
import { Plus, Trash2, Plug, RefreshCw, Server } from 'lucide-react'
import { mcpApi } from '../../api/client'

interface MCPServer {
  name: string
  command: string
  args: string[]
  status: string
  tools_count: number
}

export function MCPPanel() {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newCommand, setNewCommand] = useState('')
  const [newArgs, setNewArgs] = useState('')

  useEffect(() => { loadServers() }, [])

  async function loadServers() {
    setLoading(true)
    try {
      const data = await mcpApi.listServers()
      setServers(data)
    } catch {}
    setLoading(false)
  }

  async function handleAdd() {
    if (!newName || !newCommand) return
    const args = newArgs.split(' ').filter(Boolean)
    await mcpApi.addServer(newName, newCommand, args)
    setNewName(''); setNewCommand(''); setNewArgs(''); setShowAdd(false)
    loadServers()
  }

  async function handleRemove(name: string) {
    await mcpApi.removeServer(name)
    loadServers()
  }

  async function handleConnect(name: string) {
    await mcpApi.connect(name)
    loadServers()
  }

  return (
    <div className="h-full flex flex-col p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Server size={14} className="text-accent" />
          MCP Servers
        </h3>
        <div className="flex gap-1">
          <button onClick={loadServers} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
            <RefreshCw size={13} />
          </button>
          <button onClick={() => setShowAdd(!showAdd)} className="p-1.5 text-text-muted hover:text-accent rounded hover:bg-elevated transition-colors">
            <Plus size={13} />
          </button>
        </div>
      </div>

      {showAdd && (
        <div className="bg-elevated border border-border rounded-lg p-3 space-y-2 animate-slide-up">
          <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Server name" className="w-full bg-bg border border-border rounded px-2 py-1.5 text-xs text-text outline-none focus:border-accent" />
          <input value={newCommand} onChange={e => setNewCommand(e.target.value)} placeholder="Command (e.g. npx @modelcontextprotocol/server-filesystem)" className="w-full bg-bg border border-border rounded px-2 py-1.5 text-xs text-text font-mono outline-none focus:border-accent" />
          <input value={newArgs} onChange={e => setNewArgs(e.target.value)} placeholder="Args (space-separated)" className="w-full bg-bg border border-border rounded px-2 py-1.5 text-xs text-text font-mono outline-none focus:border-accent" />
          <div className="flex gap-2">
            <button onClick={handleAdd} className="px-3 py-1.5 bg-accent text-onAccent rounded text-xs font-medium hover:bg-accent-hover">Add</button>
            <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 bg-elevated text-text-sec rounded text-xs hover:bg-border">Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-xs text-text-muted">Loading...</div>
      ) : servers.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-xs">
          <Server size={24} className="mx-auto mb-2 opacity-30" />
          <p>No MCP servers configured</p>
          <p className="mt-1 text-text-muted/50">Add a server to extend agent capabilities</p>
        </div>
      ) : (
        <div className="space-y-2">
          {servers.map(s => (
            <div key={s.name} className="bg-elevated border border-border rounded-lg p-3 flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <div className={`w-2 h-2 rounded-full ${s.status === 'connected' ? 'bg-green-400' : 'bg-text-muted'}`} />
                <div className="min-w-0">
                  <div className="text-xs font-medium text-text">{s.name}</div>
                  <div className="text-[10px] text-text-muted font-mono truncate">{s.command}</div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-text-muted mr-1">{s.tools_count} tools</span>
                <button onClick={() => handleConnect(s.name)} className="p-1 text-text-muted hover:text-green-400 transition-colors" title="Connect">
                  <Plug size={12} />
                </button>
                <button onClick={() => handleRemove(s.name)} className="p-1 text-text-muted hover:text-red-400 transition-colors" title="Remove">
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-auto pt-2 border-t border-border">
        <p className="text-[10px] text-text-muted/50">
          MCP servers provide external tools (filesystem, GitHub, browser, databases).
          Tools are discovered automatically on connect.
        </p>
      </div>
    </div>
  )
}
