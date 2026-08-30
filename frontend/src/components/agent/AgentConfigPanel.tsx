import { useState, useEffect } from 'react'
import { Settings, Plus, Trash2, RefreshCw, ChevronDown, ChevronRight, Server, Link2, Shield } from 'lucide-react'
import { agentApi } from '../../api/client'

interface Preset {
  id: string
  name: string
  description: string
  icon: string
  max_steps: number
  max_tokens: number
  temperature: number
  auto_commit: boolean
  auto_test: boolean
  auto_verify: boolean
  allowed_tools: string[]
  blocked_tools: string[]
}

interface MCPServer {
  name: string
  command: string
  args: string[]
  status: string
  tools_count: number
}

const PRESET_ICONS: Record<string, string> = {
  research: '🔍', code_review: '📋', refactor: '🔄', debug: '🐛', full_stack: '🚀', quick_fix: '⚡',
}

export function AgentConfigPanel() {
  const [presets, setPresets] = useState<Preset[]>([])
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedSection, setExpandedSection] = useState<string | null>('presets')
  const [expandedPreset, setExpandedPreset] = useState<string | null>(null)
  const [newServerName, setNewServerName] = useState('')
  const [newServerCmd, setNewServerCmd] = useState('')
  const [newServerArgs, setNewServerArgs] = useState('')
  const [modelStatus, setModelStatus] = useState<any>(null)
  const [fallbackChain, setFallbackChain] = useState<string[]>([])

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [p, m, ms] = await Promise.all([
        agentApi.presets(),
        agentApi.mcpServers(),
        agentApi.modelStatus(),
      ])
      setPresets(p)
      setMcpServers(m)
      setModelStatus(ms)
    } catch {}
    setLoading(false)
  }

  async function handleAddServer() {
    if (!newServerName || !newServerCmd) return
    try {
      const args = newServerArgs.split(' ').filter(Boolean)
      await fetch('/api/mcp/servers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newServerName, command: newServerCmd, args }),
      })
      setNewServerName('')
      setNewServerCmd('')
      setNewServerArgs('')
      loadData()
    } catch {}
  }

  async function handleRemoveServer(name: string) {
    try {
      await fetch(`/api/mcp/servers/${name}`, { method: 'DELETE' })
      loadData()
    } catch {}
  }



  function removeFromFallback(index: number) {
    setFallbackChain(fallbackChain.filter((_, i) => i !== index))
  }

  const sections = [
    { id: 'presets', label: 'Agent Presets', icon: Settings },
    { id: 'mcp', label: 'MCP Servers', icon: Server },
    { id: 'model', label: 'Model Config', icon: Link2 },
    { id: 'tools', label: 'Tool Permissions', icon: Shield },
  ]

  return (
    <div className="h-full flex flex-col p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Settings size={14} className="text-accent" />
          Agent Config
        </h3>
        <button onClick={loadData} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Loading config...</div>
      ) : (
        <>
          {/* Section toggles */}
          <div className="space-y-1">
            {sections.map(sec => {
              const Icon = sec.icon
              const open = expandedSection === sec.id
              return (
                <div key={sec.id}>
                  <button
                    onClick={() => setExpandedSection(open ? null : sec.id)}
                    className="w-full flex items-center gap-2 px-3 py-2 bg-elevated border border-border rounded-lg text-xs font-medium text-text hover:border-accent/30 transition-colors"
                  >
                    <Icon size={13} className="text-accent" />
                    <span className="flex-1 text-left">{sec.label}</span>
                    {open ? <ChevronDown size={12} className="text-text-muted" /> : <ChevronRight size={12} className="text-text-muted" />}
                  </button>

                  {/* Section content */}
                  {open && sec.id === 'presets' && (
                    <div className="ml-2 mt-1 space-y-1.5">
                      {presets.map(p => (
                        <div key={p.id} className="bg-elevated border border-border rounded-lg overflow-hidden">
                          <button
                            onClick={() => setExpandedPreset(expandedPreset === p.id ? null : p.id)}
                            className="w-full flex items-center gap-2 px-3 py-2 text-left"
                          >
                            <span className="text-sm">{PRESET_ICONS[p.id] || '🔧'}</span>
                            <div className="flex-1 min-w-0">
                              <div className="text-[11px] font-medium text-text">{p.name}</div>
                              <div className="text-[9px] text-text-muted truncate">{p.description}</div>
                            </div>
                            <div className="text-[9px] text-text-muted">{p.max_steps} steps</div>
                          </button>
                          {expandedPreset === p.id && (
                            <div className="px-3 pb-2 space-y-1.5 border-t border-border/50">
                              <div className="grid grid-cols-2 gap-1.5 mt-2">
                                <div className="bg-bg rounded px-2 py-1">
                                  <span className="text-[8px] text-text-muted">Max Steps</span>
                                  <div className="text-[10px] text-text">{p.max_steps}</div>
                                </div>
                                <div className="bg-bg rounded px-2 py-1">
                                  <span className="text-[8px] text-text-muted">Temperature</span>
                                  <div className="text-[10px] text-text">{p.temperature}</div>
                                </div>
                                <div className="bg-bg rounded px-2 py-1">
                                  <span className="text-[8px] text-text-muted">Max Tokens</span>
                                  <div className="text-[10px] text-text">{p.max_tokens.toLocaleString()}</div>
                                </div>
                                <div className="bg-bg rounded px-2 py-1">
                                  <span className="text-[8px] text-text-muted">Auto-commit</span>
                                  <div className="text-[10px] text-text">{p.auto_commit ? '✓' : '✗'}</div>
                                </div>
                              </div>
                              {p.allowed_tools.length > 0 && (
                                <div className="text-[9px] text-text-muted">Allowed: {p.allowed_tools.join(', ')}</div>
                              )}
                              {p.blocked_tools.length > 0 && (
                                <div className="text-[9px] text-red-400">Blocked: {p.blocked_tools.join(', ')}</div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {open && sec.id === 'mcp' && (
                    <div className="ml-2 mt-1 space-y-1.5">
                      {mcpServers.map(s => (
                        <div key={s.name} className="bg-elevated border border-border rounded-lg px-3 py-2 flex items-center justify-between">
                          <div className="min-w-0 flex-1">
                            <div className="text-[11px] font-medium text-text">{s.name}</div>
                            <div className="text-[9px] text-text-muted font-mono truncate">{s.command} {(s.args || []).join(' ')}</div>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className={`text-[8px] px-1.5 py-0.5 rounded ${(s as any).connected ? 'bg-green-500/10 text-green-400' : 'bg-elevated text-text-muted'}`}>
                              {(s as any).connected ? 'Connected' : s.status}
                            </span>
                            <button onClick={() => handleRemoveServer(s.name)} className="p-0.5 text-text-muted hover:text-red-400 transition-colors">
                              <Trash2 size={11} />
                            </button>
                          </div>
                        </div>
                      ))}

                      {/* Add new server */}
                      <div className="bg-bg border border-border border-dashed rounded-lg px-3 py-2 space-y-1.5">
                        <div className="text-[9px] text-text-muted uppercase">Add MCP Server</div>
                        <input
                          placeholder="Server name"
                          value={newServerName}
                          onChange={(e) => setNewServerName(e.target.value)}
                          className="w-full bg-elevated border border-border rounded px-2 py-1 text-[10px] text-text outline-none focus:border-accent"
                        />
                        <input
                          placeholder="Command (e.g. npx)"
                          value={newServerCmd}
                          onChange={(e) => setNewServerCmd(e.target.value)}
                          className="w-full bg-elevated border border-border rounded px-2 py-1 text-[10px] text-text outline-none focus:border-accent"
                        />
                        <input
                          placeholder="Args (space-separated)"
                          value={newServerArgs}
                          onChange={(e) => setNewServerArgs(e.target.value)}
                          className="w-full bg-elevated border border-border rounded px-2 py-1 text-[10px] text-text outline-none focus:border-accent"
                        />
                        <button
                          onClick={handleAddServer}
                          disabled={!newServerName || !newServerCmd}
                          className="w-full flex items-center justify-center gap-1 px-2 py-1 bg-accent/10 text-accent rounded text-[10px] hover:bg-accent/20 disabled:opacity-30 transition-colors"
                        >
                          <Plus size={10} /> Add Server
                        </button>
                      </div>
                    </div>
                  )}

                  {open && sec.id === 'model' && (
                    <div className="ml-2 mt-1 space-y-2">
                      {/* Current model */}
                      <div className="bg-elevated border border-border rounded-lg px-3 py-2">
                        <div className="text-[9px] text-text-muted uppercase mb-1">Active Model</div>
                        {modelStatus?.loaded ? (
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-success" />
                            <span className="text-[10px] text-text truncate">{modelStatus.path || 'Unknown'}</span>
                          </div>
                        ) : (
                          <span className="text-[10px] text-text-muted">No model loaded</span>
                        )}
                      </div>

                      {/* Fallback chain */}
                      <div className="bg-elevated border border-border rounded-lg px-3 py-2">
                        <div className="text-[9px] text-text-muted uppercase mb-1">Fallback Chain</div>
                        <div className="space-y-1">
                          {fallbackChain.map((path, i) => (
                            <div key={i} className="flex items-center gap-2 bg-bg rounded px-2 py-1">
                              <span className="text-[8px] text-text-muted">{i + 1}.</span>
                              <span className="text-[10px] text-text flex-1 truncate font-mono">{path.split(/[/\\]/).pop()}</span>
                              <button onClick={() => removeFromFallback(i)} className="text-text-muted hover:text-red-400 transition-colors">
                                <Trash2 size={9} />
                              </button>
                            </div>
                          ))}
                          {fallbackChain.length === 0 && (
                            <div className="text-[9px] text-text-muted/50 italic">No fallback models configured</div>
                          )}
                        </div>
                        <div className="text-[9px] text-text-muted mt-1">
                          Models are tried in order if the primary fails to load
                        </div>
                      </div>
                    </div>
                  )}

                  {open && sec.id === 'tools' && (
                    <div className="ml-2 mt-1 space-y-1.5">
                      <div className="bg-elevated border border-border rounded-lg px-3 py-2">
                        <div className="text-[9px] text-text-muted uppercase mb-1.5">Global Tool Permissions</div>
                        <div className="space-y-1">
                          {['read_file', 'write_file', 'edit_file', 'run_command', 'git', 'run_python', 'glob', 'search_files'].map(tool => (
                            <div key={tool} className="flex items-center justify-between bg-bg rounded px-2 py-1">
                              <span className="text-[10px] text-text font-mono">{tool}</span>
                              <div className="flex items-center gap-1.5">
                                <span className="text-[8px] text-text-muted">
                                  {['run_command', 'git', 'run_python', 'write_file', 'edit_file'].includes(tool) ? 'approval' : 'auto'}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="text-[9px] text-text-muted mt-1.5">
                          Approval-gated tools require user confirmation before execution
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
