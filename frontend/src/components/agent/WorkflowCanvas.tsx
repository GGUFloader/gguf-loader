import { useState, useRef, useCallback, useEffect } from 'react'
import { workflowsApi } from '../../api/client'
import { Trash2, Play, CheckCircle, Zap, GitBranch, Settings, ArrowRight } from 'lucide-react'

interface Node {
  id: string
  type: 'llm' | 'tool' | 'condition' | 'transform'
  name: string
  x: number
  y: number
  config: Record<string, any>
  dependsOn: string[]
}

interface Edge {
  id: string
  from: string
  to: string
  condition?: string
}

const TYPE_COLORS: Record<string, { bg: string; border: string; icon: any }> = {
  llm: { bg: 'bg-blue-500/20', border: 'border-blue-500', icon: Zap },
  tool: { bg: 'bg-amber-500/20', border: 'border-amber-500', icon: Settings },
  condition: { bg: 'bg-purple-500/20', border: 'border-purple-500', icon: GitBranch },
  transform: { bg: 'bg-emerald-500/20', border: 'border-emerald-500', icon: ArrowRight },
}

export function WorkflowCanvas() {
  const [workflows, setWorkflows] = useState<any[]>([])
  const [activeWf, setActiveWf] = useState<any>(null)
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [dragging, setDragging] = useState<string | null>(null)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const [connecting, setConnecting] = useState<string | null>(null)
  const [showAddMenu, setShowAddMenu] = useState(false)
  const [addPos, setAddPos] = useState({ x: 0, y: 0 })
  const svgRef = useRef<SVGSVGElement>(null)
  const [status, setStatus] = useState<string | null>(null)

  const loadWorkflows = useCallback(async () => {
    try {
      const wfs = await workflowsApi.list()
      setWorkflows(wfs)
    } catch { /* ok */ }
  }, [])

  useEffect(() => { loadWorkflows() }, [loadWorkflows])

  const loadWorkflow = async (id: string) => {
    try {
      const wf = await workflowsApi.get(id)
      setActiveWf(wf)
      const loadedNodes: Node[] = (wf.steps || []).map((s: any, i: number) => ({
        id: s.id,
        type: s.type || 'llm',
        name: s.name || s.id,
        x: 80 + (i % 3) * 200,
        y: 60 + Math.floor(i / 3) * 140,
        config: s.config || {},
        dependsOn: s.depends_on || [],
      }))
      const loadedEdges: Edge[] = []
      for (const n of loadedNodes) {
        for (const dep of n.dependsOn) {
          loadedEdges.push({ id: `${dep}-${n.id}`, from: dep, to: n.id })
        }
      }
      setNodes(loadedNodes)
      setEdges(loadedEdges)
      setSelectedNode(null)
    } catch { /* ok */ }
  }

  const toScreen = (x: number, y: number) => ({ x: x + 50, y: y + 50 })

  const handleMouseDown = (e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation()
    if (connecting) {
      // Complete connection
      if (connecting !== nodeId) {
        setEdges(prev => [...prev, { id: `${connecting}-${nodeId}`, from: connecting, to: nodeId }])
        setNodes(prev => prev.map(n =>
          n.id === nodeId ? { ...n, dependsOn: [...n.dependsOn, connecting] } : n
        ))
      }
      setConnecting(null)
      return
    }
    const node = nodes.find(n => n.id === nodeId)
    if (!node) return
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return
    setDragOffset({ x: e.clientX - rect.left - node.x, y: e.clientY - rect.top - node.y })
    setDragging(nodeId)
    setSelectedNode(nodeId)
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragging || !svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left - dragOffset.x
    const y = e.clientY - rect.top - dragOffset.y
    setNodes(prev => prev.map(n => n.id === dragging ? { ...n, x: Math.max(0, x - 50), y: Math.max(0, y - 50) } : n))
  }

  const handleMouseUp = () => { setDragging(null) }

  const handleCanvasClick = (e: React.MouseEvent) => {
    if (connecting) { setConnecting(null); return }
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return
    setAddPos({ x: e.clientX - rect.left - 50, y: e.clientY - rect.top - 50 })
    setShowAddMenu(true)
  }

  const addNode = (type: Node['type']) => {
    const id = `step_${Date.now()}`
    const names: Record<string, string> = { llm: 'LLM Call', tool: 'Tool Use', condition: 'Condition', transform: 'Transform' }
    setNodes(prev => [...prev, { id, type, name: names[type], x: addPos.x, y: addPos.y, config: {}, dependsOn: [] }])
    setShowAddMenu(false)
    setSelectedNode(id)
  }

  const deleteNode = (nodeId: string) => {
    setNodes(prev => prev.filter(n => n.id !== nodeId))
    setEdges(prev => prev.filter(e => e.from !== nodeId && e.to !== nodeId))
    setNodes(prev => prev.map(n => ({ ...n, dependsOn: n.dependsOn.filter(d => d !== nodeId) })))
    setSelectedNode(null)
  }

  const updateNodeName = (nodeId: string, name: string) => {
    setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, name } : n))
  }

  const saveWorkflow = async () => {
    if (!activeWf) return
    const steps = nodes.map(n => ({
      id: n.id, type: n.type, name: n.name, config: n.config,
      depends_on: n.dependsOn, outputs: [],
    }))
    try {
      await workflowsApi.updateSteps(activeWf.id, steps)
      setStatus('Saved!')
      setTimeout(() => setStatus(null), 2000)
    } catch {
      setStatus('Save failed')
      setTimeout(() => setStatus(null), 2000)
    }
  }

  const runWorkflow = async () => {
    if (!activeWf) return
    try {
      await workflowsApi.run(activeWf.id)
      setStatus('Running...')
      setTimeout(() => setStatus(null), 3000)
    } catch { /* ok */ }
  }

  const validateWorkflow = async () => {
    if (!activeWf) return
    try {
      const result = await workflowsApi.validate(activeWf.id)
      setStatus(result.valid ? 'Valid ✓' : `Errors: ${(result.errors || []).join(', ')}`)
      setTimeout(() => setStatus(null), 3000)
    } catch { /* ok */ }
  }

  const selectedNodeData = nodes.find(n => n.id === selectedNode)

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 p-2 border-b border-border">
        <select
          className="bg-elevated border border-border rounded px-2 py-1 text-xs text-text"
          value={activeWf?.id || ''}
          onChange={(e) => e.target.value && loadWorkflow(e.target.value)}
        >
          <option value="">Select workflow...</option>
          {workflows.map(wf => (
            <option key={wf.id} value={wf.id}>{wf.name}</option>
          ))}
        </select>
        {activeWf && (
          <>
            <button onClick={saveWorkflow} className="text-xs px-2 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30">
              Save
            </button>
            <button onClick={runWorkflow} className="text-xs px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded hover:bg-emerald-500/30">
              <Play size={12} className="inline mr-1" />Run
            </button>
            <button onClick={validateWorkflow} className="text-xs px-2 py-1 bg-purple-500/20 text-purple-400 rounded hover:bg-purple-500/30">
              <CheckCircle size={12} className="inline mr-1" />Validate
            </button>
          </>
        )}
        {status && <span className="text-xs text-accent ml-auto">{status}</span>}
      </div>

      {/* Canvas */}
      <div className="flex-1 relative overflow-hidden bg-[#0d1117]">
        {nodes.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-text-muted text-sm">
            {activeWf ? 'Click to add workflow steps' : 'Select a workflow to edit'}
          </div>
        ) : (
          <svg
            ref={svgRef}
            className="w-full h-full"
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onClick={handleCanvasClick}
          >
            <defs>
              <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill="#6b7280" />
              </marker>
              <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                <circle cx="10" cy="10" r="0.5" fill="#1e293b" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />

            {/* Edges */}
            {edges.map(edge => {
              const from = nodes.find(n => n.id === edge.from)
              const to = nodes.find(n => n.id === edge.to)
              if (!from || !to) return null
              const fp = toScreen(from.x + 70, from.y + 30)
              const tp = toScreen(to.x + 70, to.y + 30)
              const mx = (fp.x + tp.x) / 2
              return (
                <g key={edge.id}>
                  <path
                    d={`M${fp.x},${fp.y} C${mx},${fp.y} ${mx},${tp.y} ${tp.x},${tp.y}`}
                    fill="none"
                    stroke="#4b5563"
                    strokeWidth="2"
                    markerEnd="url(#arrowhead)"
                    className="cursor-pointer hover:stroke-accent"
                    onClick={(e) => {
                      e.stopPropagation()
                      setEdges(prev => prev.filter(ed => ed.id !== edge.id))
                    }}
                  />
                </g>
              )
            })}

            {/* Connecting line */}
            {connecting && (() => {
              const from = nodes.find(n => n.id === connecting)
              if (!from) return null
              const fp = toScreen(from.x + 70, from.y + 30)
              return <line x1={fp.x} y1={fp.y} x2={fp.x + 50} y2={fp.y} stroke="#f59e0b" strokeWidth="2" strokeDasharray="5,5" />
            })()}

            {/* Nodes */}
            {nodes.map(node => {
              const style = TYPE_COLORS[node.type] || TYPE_COLORS.llm
              const Icon = style.icon
              const pos = toScreen(node.x, node.y)
              const isSelected = selectedNode === node.id
              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x - 70}, ${pos.y - 30})`}
                  onMouseDown={(e) => handleMouseDown(e, node.id)}
                  className="cursor-grab active:cursor-grabbing"
                >
                  <rect
                    x="0" y="0" width="140" height="60" rx="8"
                    fill={isSelected ? '#1e3a5f' : '#161b22'}
                    stroke={isSelected ? '#3b82f6' : style.border.replace('border-', '#')}
                    strokeWidth={isSelected ? 2 : 1}
                    className="transition-all"
                  />
                  <foreignObject x="8" y="8" width="24" height="24">
                    <Icon size={16} className={isSelected ? 'text-accent' : 'text-text-sec'} />
                  </foreignObject>
                  <text x="36" y="20" fill={isSelected ? '#e2e8f0' : '#94a3b8'} fontSize="11" fontWeight="600">
                    {node.name.length > 14 ? node.name.slice(0, 14) + '…' : node.name}
                  </text>
                  <text x="36" y="36" fill="#64748b" fontSize="9">
                    {node.type}
                  </text>
                  {/* Connection handle */}
                  <circle
                    cx="140" cy="30" r="5"
                    fill={connecting === node.id ? '#f59e0b' : '#374151'}
                    stroke="#6b7280"
                    strokeWidth="1"
                    className="cursor-pointer hover:fill-accent"
                    onMouseDown={(e) => {
                      e.stopPropagation()
                      setConnecting(node.id)
                    }}
                  />
                </g>
              )
            })}
          </svg>
        )}

        {/* Add node menu */}
        {showAddMenu && (
          <div
            className="absolute bg-elevated border border-border rounded-lg shadow-lg p-1 z-10"
            style={{ left: addPos.x + 50, top: addPos.y + 50 }}
          >
            {(['llm', 'tool', 'condition', 'transform'] as const).map(type => {
              const style = TYPE_COLORS[type]
              const Icon = style.icon
              return (
                <button
                  key={type}
                  onClick={() => addNode(type)}
                  className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-text hover:bg-surface rounded"
                >
                  <Icon size={12} className="text-text-sec" />
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </button>
              )
            })}
            <button onClick={() => setShowAddMenu(false)} className="w-full px-3 py-1 text-[10px] text-text-muted mt-1 hover:text-text">
              Cancel
            </button>
          </div>
        )}
      </div>

      {/* Node editor panel */}
      {selectedNodeData && (
        <div className="border-t border-border bg-surface p-3">
          <div className="flex items-center gap-2 mb-2">
            <input
              value={selectedNodeData.name}
              onChange={(e) => updateNodeName(selectedNodeData.id, e.target.value)}
              className="flex-1 bg-elevated border border-border rounded px-2 py-1 text-sm text-text"
            />
            <button
              onClick={() => deleteNode(selectedNodeData.id)}
              className="p-1 text-danger hover:bg-danger/20 rounded"
            >
              <Trash2 size={14} />
            </button>
          </div>
          <div className="text-[10px] text-text-muted">
            Type: {selectedNodeData.type} · Dependencies: {selectedNodeData.dependsOn.length || 'none'}
            {connecting && <span className="ml-2 text-amber-400">Click another node to connect</span>}
          </div>
        </div>
      )}
    </div>
  )
}
