import { useState, useEffect, useCallback, useRef } from 'react'
import { sandboxApi } from '../../api/client'
import { Shield, Upload, Play, Trash2, Activity, AlertTriangle, CheckCircle, XCircle, Clock, MemoryStick, RefreshCw, Box, Terminal } from 'lucide-react'

interface PluginFile {
  name: string
  path: string
  size_bytes: number
  manifest: any
}

interface PluginInstance {
  id: string
  manifest: { name: string; version: string; description: string; permissions: string[]; resource_limits: any }
  state: string
  calls_count: number
  total_cpu_ms: number
  total_memory_bytes: number
  last_error: string | null
  loaded_at: number
}

const STATE_COLORS: Record<string, { color: string; icon: any }> = {
  loaded: { color: 'text-emerald-400', icon: CheckCircle },
  running: { color: 'text-blue-400', icon: Activity },
  stopped: { color: 'text-text-muted', icon: XCircle },
  error: { color: 'text-danger', icon: AlertTriangle },
  timed_out: { color: 'text-amber-400', icon: Clock },
  oom: { color: 'text-red-400', icon: MemoryStick },
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function PluginSandboxPanel() {
  const [view, setView] = useState<'files' | 'instances' | 'call'>('files')
  const [files, setFiles] = useState<PluginFile[]>([])
  const [instances, setInstances] = useState<PluginInstance[]>([])
  const [status, setStatus] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedInstance, setSelectedInstance] = useState<string | null>(null)

  // Call form state
  const [callFn, setCallFn] = useState('process')
  const [callInput, setCallInput] = useState('{\n  "input": "hello"\n}')
  const [callTimeout, setCallTimeout] = useState(30)
  const [callResult, setCallResult] = useState<any>(null)
  const [calling, setCalling] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadData = useCallback(async () => {
    try {
      const [s, f, i] = await Promise.all([
        sandboxApi.status(),
        sandboxApi.plugins(),
        sandboxApi.instances(),
      ])
      setStatus(s)
      setFiles(f)
      setInstances(i)
    } catch { /* ok */ }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      await sandboxApi.upload(file)
      await loadData()
    } catch (err: any) {
      setError(err.message || 'Upload failed')
    }
    setLoading(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const loadPlugin = async (path: string) => {
    setLoading(true)
    setError(null)
    try {
      await sandboxApi.load(path)
      await loadData()
    } catch (err: any) {
      setError(err.message || 'Load failed')
    }
    setLoading(false)
  }

  const unloadPlugin = async (id: string) => {
    try {
      await sandboxApi.unload(id)
      if (selectedInstance === id) setSelectedInstance(null)
      await loadData()
    } catch { /* ok */ }
  }

  const callPlugin = async () => {
    if (!selectedInstance) return
    setCalling(true)
    setCallResult(null)
    setError(null)
    try {
      const input = JSON.parse(callInput)
      const result = await sandboxApi.call(selectedInstance, callFn, input, callTimeout * 1000)
      setCallResult(result)
    } catch (err: any) {
      setError(err.message || 'Call failed')
    }
    setCalling(false)
  }

  const deleteFile = async (filename: string) => {
    try {
      await sandboxApi.deleteFile(filename)
      await loadData()
    } catch { /* ok */ }
  }

  const selectedInst = instances.find(i => i.id === selectedInstance)

  return (
    <div className="h-full flex flex-col">
      {/* Header tabs */}
      <div className="flex border-b border-border">
        {([
          { id: 'files' as const, label: 'Plugins', icon: Box },
          { id: 'instances' as const, label: 'Running', icon: Activity },
          { id: 'call' as const, label: 'Test', icon: Terminal },
        ]).map(tab => (
          <button
            key={tab.id}
            onClick={() => setView(tab.id)}
            className={`flex-1 flex items-center justify-center gap-1 py-2 text-[11px] font-medium transition-colors ${
              view === tab.id ? 'text-accent border-b-2 border-accent' : 'text-text-muted hover:text-text-sec'
            }`}
          >
            <tab.icon size={12} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Status bar */}
      {status && (
        <div className="flex items-center gap-3 px-3 py-1.5 bg-surface border-b border-border text-[10px] text-text-muted">
          <span className="flex items-center gap-1">
            <Shield size={10} className="text-emerald-400" />
            Runtime: {status.runtime}
          </span>
          <span>{status.instance_count} instance{status.instance_count !== 1 ? 's' : ''}</span>
          <span>{status.total_calls} calls</span>
          <span>{formatMs(status.total_cpu_ms)} total CPU</span>
          <button onClick={loadData} className="ml-auto p-0.5 hover:text-text"><RefreshCw size={10} /></button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mx-3 mt-2 px-3 py-2 bg-danger/10 border border-danger/30 rounded text-xs text-danger flex items-center gap-2">
          <AlertTriangle size={12} />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-danger/50 hover:text-danger">×</button>
        </div>
      )}

      <div className="flex-1 overflow-auto">
        {/* Plugins directory */}
        {view === 'files' && (
          <div className="p-3 space-y-3">
            {/* Upload */}
            <div className="flex gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".wasm"
                onChange={handleUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/20 text-accent rounded text-xs hover:bg-accent/30 disabled:opacity-50"
              >
                <Upload size={12} />
                Upload .wasm
              </button>
            </div>

            {/* Plugin files */}
            {files.length === 0 ? (
              <div className="text-center py-8 text-text-muted text-xs">
                <Box size={24} className="mx-auto mb-2 opacity-50" />
                No WASM plugins found
                <div className="mt-1 text-[10px]">Upload a .wasm file to get started</div>
              </div>
            ) : (
              files.map(f => (
                <div key={f.name} className="bg-elevated rounded-lg p-3 border border-border">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Box size={14} className="text-amber-400" />
                      <div>
                        <div className="text-sm text-text font-medium">{f.name}</div>
                        <div className="text-[10px] text-text-muted">
                          {formatBytes(f.size_bytes)}
                          {f.manifest && ` · v${f.manifest.version}`}
                          {f.manifest?.author && ` · ${f.manifest.author}`}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-1.5">
                      <button
                        onClick={() => loadPlugin(f.path)}
                        disabled={loading}
                        className="text-[10px] px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded hover:bg-emerald-500/30 disabled:opacity-50"
                      >
                        Load
                      </button>
                      <button
                        onClick={() => deleteFile(f.name)}
                        className="text-[10px] px-2 py-1 bg-danger/20 text-danger rounded hover:bg-danger/30"
                      >
                        <Trash2 size={10} />
                      </button>
                    </div>
                  </div>
                  {f.manifest?.description && (
                    <div className="text-[10px] text-text-sec mt-1">{f.manifest.description}</div>
                  )}
                  {f.manifest?.permissions?.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      {f.manifest.permissions.map((p: string, i: number) => (
                        <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          {p}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Running instances */}
        {view === 'instances' && (
          <div className="p-3 space-y-3">
            {instances.length === 0 ? (
              <div className="text-center py-8 text-text-muted text-xs">
                <Activity size={24} className="mx-auto mb-2 opacity-50" />
                No running instances
              </div>
            ) : (
              instances.map(inst => {
                const stateStyle = STATE_COLORS[inst.state] || STATE_COLORS.loaded
                const StateIcon = stateStyle.icon
                const isSelected = selectedInstance === inst.id
                const limits = inst.manifest.resource_limits || {}
                const cpuPct = limits.max_cpu_time_ms ? (inst.total_cpu_ms / limits.max_cpu_time_ms * 100) : 0
                const memPct = limits.max_memory_bytes ? (inst.total_memory_bytes / limits.max_memory_bytes * 100) : 0

                return (
                  <div
                    key={inst.id}
                    onClick={() => setSelectedInstance(isSelected ? null : inst.id)}
                    className={`bg-elevated rounded-lg p-3 border cursor-pointer transition-colors ${
                      isSelected ? 'border-accent' : 'border-border hover:border-border/80'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <StateIcon size={14} className={stateStyle.color} />
                        <div>
                          <div className="text-sm text-text font-medium">{inst.manifest.name}</div>
                          <div className="text-[10px] text-text-muted">v{inst.manifest.version} · {inst.state}</div>
                        </div>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); unloadPlugin(inst.id) }}
                        className="text-[10px] px-2 py-1 bg-danger/20 text-danger rounded hover:bg-danger/30"
                      >
                        Stop
                      </button>
                    </div>

                    {/* Resource bars */}
                    <div className="mt-3 space-y-1.5">
                      <div>
                        <div className="flex justify-between text-[9px] text-text-muted mb-0.5">
                          <span>CPU: {formatMs(inst.total_cpu_ms)}</span>
                          <span>{cpuPct.toFixed(1)}%</span>
                        </div>
                        <div className="h-1 bg-surface rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all"
                            style={{ width: `${Math.min(cpuPct, 100)}%` }}
                          />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-[9px] text-text-muted mb-0.5">
                          <span>Memory: {formatBytes(inst.total_memory_bytes)}</span>
                          <span>{memPct.toFixed(1)}%</span>
                        </div>
                        <div className="h-1 bg-surface rounded-full overflow-hidden">
                          <div
                            className="h-full bg-amber-500 rounded-full transition-all"
                            style={{ width: `${Math.min(memPct, 100)}%` }}
                          />
                        </div>
                      </div>
                      <div className="text-[9px] text-text-muted">
                        Calls: {inst.calls_count}/{limits.max_calls || '∞'}
                      </div>
                    </div>

                    {inst.last_error && (
                      <div className="mt-2 text-[10px] text-danger bg-danger/5 rounded p-1.5">
                        {inst.last_error}
                      </div>
                    )}

                    {/* Permissions */}
                    {inst.manifest.permissions?.length > 0 && (
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {inst.manifest.permissions.map((p: string, i: number) => (
                          <span key={i} className="text-[9px] px-1 py-0.5 rounded bg-surface text-text-muted">
                            {p}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        )}

        {/* Call tester */}
        {view === 'call' && (
          <div className="p-3 space-y-3">
            {!selectedInstance ? (
              <div className="text-center py-8 text-text-muted text-xs">
                <Terminal size={24} className="mx-auto mb-2 opacity-50" />
                Select an instance from the Running tab first
              </div>
            ) : (
              <>
                <div className="bg-elevated rounded-lg p-3 border border-border">
                  <div className="text-xs text-text font-medium mb-2">
                    Call: {selectedInst?.manifest.name}
                  </div>

                  <div className="space-y-2">
                    <div>
                      <label className="text-[10px] text-text-muted">Function</label>
                      <input
                        value={callFn}
                        onChange={(e) => setCallFn(e.target.value)}
                        className="w-full bg-surface border border-border rounded px-2 py-1 text-xs text-text mt-0.5"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-text-muted">Input (JSON)</label>
                      <textarea
                        value={callInput}
                        onChange={(e) => setCallInput(e.target.value)}
                        rows={5}
                        className="w-full bg-surface border border-border rounded px-2 py-1 text-xs text-text font-mono mt-0.5"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-text-muted">Timeout (seconds)</label>
                      <input
                        type="number"
                        value={callTimeout}
                        onChange={(e) => setCallTimeout(Number(e.target.value))}
                        className="w-20 bg-surface border border-border rounded px-2 py-1 text-xs text-text mt-0.5"
                      />
                    </div>
                    <button
                      onClick={callPlugin}
                      disabled={calling}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/20 text-accent rounded text-xs hover:bg-accent/30 disabled:opacity-50"
                    >
                      {calling ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                      {calling ? 'Running...' : 'Execute'}
                    </button>
                  </div>
                </div>

                {/* Result */}
                {callResult && (
                  <div className={`rounded-lg p-3 border ${
                    callResult.success ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-danger/5 border-danger/20'
                  }`}>
                    <div className="flex items-center gap-2 mb-2">
                      {callResult.success ? (
                        <CheckCircle size={12} className="text-emerald-400" />
                      ) : (
                        <XCircle size={12} className="text-danger" />
                      )}
                      <span className="text-xs font-medium text-text">
                        {callResult.success ? 'Success' : 'Failed'}
                      </span>
                      <span className="text-[10px] text-text-muted ml-auto">
                        {formatMs(callResult.cpu_ms)}
                      </span>
                    </div>
                    {callResult.output !== null && callResult.output !== undefined && (
                      <pre className="text-[10px] text-text-sec font-mono whitespace-pre-wrap overflow-auto max-h-48">
                        {typeof callResult.output === 'string'
                          ? callResult.output
                          : JSON.stringify(callResult.output, null, 2)}
                      </pre>
                    )}
                    {callResult.error && (
                      <div className="text-[10px] text-danger mt-1">{callResult.error}</div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
