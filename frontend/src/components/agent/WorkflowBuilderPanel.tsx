import { useState, useEffect } from 'react'
import { GitBranch, Copy, Trash2, RefreshCw, Check, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react'

interface WorkflowStep {
  id: string
  type: string
  name: string
  config: Record<string, any>
  depends_on: string[]
}

interface Workflow {
  id: string
  name: string
  description: string
  steps: WorkflowStep[]
  tags: string[]
  created_at: number
  updated_at: number
}

interface WorkflowTemplate {
  id: string
  name: string
  description: string
}

const STEP_TYPE_COLORS: Record<string, string> = {
  llm: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  tool: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  condition: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  transform: 'bg-green-500/10 text-green-400 border-green-500/20',
}

export function WorkflowBuilderPanel() {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null)
  const [expandedStep, setExpandedStep] = useState<string | null>(null)
  const [validationResult, setValidationResult] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<'workflows' | 'templates'>('workflows')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [w, t] = await Promise.all([
        fetch('/api/agent/workflows').then(r => r.json()),
        fetch('/api/agent/workflows/templates').then(r => r.json()),
      ])
      setWorkflows(w)
      setTemplates(t)
    } catch {}
    setLoading(false)
  }

  async function handleCreateFromTemplate(templateId: string) {
    try {
      const res = await fetch(`/api/agent/workflows/${templateId}/from-template`, { method: 'POST', body: '{}' })
      const data = await res.json()
      if (data.id) {
        loadData()
        setSelectedWorkflow(data)
      }
    } catch {}
  }

  async function handleValidate(workflow: Workflow) {
    try {
      const res = await fetch(`/api/agent/workflows/${workflow.id}/validate`, { method: 'POST' })
      setValidationResult(await res.json())
    } catch {}
  }

  async function handleDelete(id: string) {
    try {
      await fetch(`/api/agent/workflows/${id}`, { method: 'DELETE' })
      setSelectedWorkflow(null)
      loadData()
    } catch {}
  }

  async function handleDuplicate(id: string) {
    try {
      await fetch(`/api/agent/workflows/${id}/duplicate`, { method: 'POST' })
      loadData()
    } catch {}
  }

  return (
    <div className="h-full flex flex-col p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <GitBranch size={14} className="text-accent" />
          Workflows
        </h3>
        <button onClick={loadData} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-elevated rounded-lg p-0.5">
        <button onClick={() => setActiveTab('workflows')}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'workflows' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
          My Workflows ({workflows.length})
        </button>
        <button onClick={() => setActiveTab('templates')}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'templates' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
          Templates ({templates.length})
        </button>
      </div>

      {loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Loading...</div>
      ) : activeTab === 'templates' ? (
        <div className="space-y-1.5">
          {templates.map(t => (
            <div key={t.id} className="bg-elevated border border-border rounded-lg px-3 py-2 flex items-center justify-between">
              <div>
                <div className="text-xs font-medium text-text">{t.name}</div>
                <div className="text-[9px] text-text-muted">{t.description}</div>
              </div>
              <button onClick={() => handleCreateFromTemplate(t.id)}
                className="px-2 py-1 bg-accent/10 text-accent rounded text-[10px] hover:bg-accent/20 transition-colors">
                Use
              </button>
            </div>
          ))}
        </div>
      ) : selectedWorkflow ? (
        /* Workflow detail view */
        <div className="space-y-3">
          <button onClick={() => { setSelectedWorkflow(null); setValidationResult(null) }}
            className="text-[11px] text-accent hover:text-accent-hover">← Back to list</button>

          <div className="bg-elevated border border-border rounded-lg px-3 py-2">
            <div className="text-xs font-medium text-text">{selectedWorkflow.name}</div>
            <div className="text-[9px] text-text-muted">{selectedWorkflow.description}</div>
            <div className="flex items-center gap-2 mt-1.5">
              <span className="text-[8px] text-text-muted">{selectedWorkflow.steps.length} steps</span>
              {selectedWorkflow.tags.map(tag => (
                <span key={tag} className="text-[8px] px-1.5 py-0.5 bg-bg rounded text-text-muted">{tag}</span>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button onClick={() => handleValidate(selectedWorkflow)}
              className="flex items-center gap-1 px-2 py-1.5 bg-elevated border border-border rounded-lg text-[10px] text-text-sec hover:border-accent/30 transition-colors">
              <Check size={10} /> Validate
            </button>
            <button onClick={() => handleDuplicate(selectedWorkflow.id)}
              className="flex items-center gap-1 px-2 py-1.5 bg-elevated border border-border rounded-lg text-[10px] text-text-sec hover:border-accent/30 transition-colors">
              <Copy size={10} /> Duplicate
            </button>
            <button onClick={() => handleDelete(selectedWorkflow.id)}
              className="flex items-center gap-1 px-2 py-1.5 bg-elevated border border-border rounded-lg text-[10px] text-red-400 hover:border-red-500/30 transition-colors">
              <Trash2 size={10} /> Delete
            </button>
          </div>

          {/* Validation result */}
          {validationResult && (
            <div className={`rounded-lg px-3 py-2 ${validationResult.valid ? 'bg-green-500/5 border border-green-500/20' : 'bg-red-500/5 border border-red-500/20'}`}>
              {validationResult.valid ? (
                <div className="text-[10px] text-green-400 flex items-center gap-1"><Check size={10} /> Valid workflow</div>
              ) : (
                <div className="space-y-0.5">
                  {validationResult.errors.map((e: string, i: number) => (
                    <div key={i} className="text-[10px] text-red-400 flex items-center gap-1"><AlertTriangle size={9} /> {e}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Steps */}
          <div className="space-y-1.5">
            {selectedWorkflow.steps.map(step => (
              <div key={step.id} className="bg-elevated border border-border rounded-lg overflow-hidden">
                <button onClick={() => setExpandedStep(expandedStep === step.id ? null : step.id)}
                  className="w-full text-left px-3 py-2 flex items-center gap-2">
                  <span className={`text-[8px] px-1.5 py-0.5 rounded border ${STEP_TYPE_COLORS[step.type] || 'bg-elevated text-text-muted border-border'}`}>
                    {step.type}
                  </span>
                  <span className="text-[10px] text-text flex-1">{step.name}</span>
                  {step.depends_on.length > 0 && (
                    <span className="text-[8px] text-text-muted">→ {step.depends_on.join(', ')}</span>
                  )}
                  {expandedStep === step.id ? <ChevronDown size={10} className="text-text-muted" /> : <ChevronRight size={10} className="text-text-muted" />}
                </button>
                {expandedStep === step.id && (
                  <div className="px-3 pb-2 border-t border-border/50 space-y-1 mt-1">
                    <div className="text-[9px] text-text-muted">Config:</div>
                    <pre className="text-[8px] text-text-sec font-mono bg-bg rounded px-2 py-1 max-h-24 overflow-y-auto">
                      {JSON.stringify(step.config, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* Workflow list */
        <div className="space-y-1.5">
          {workflows.length === 0 ? (
            <div className="text-center py-8 text-text-muted text-xs">
              <GitBranch size={24} className="mx-auto mb-2 opacity-30" />
              <p>No workflows yet</p>
              <p className="mt-1 text-text-muted/50">Create one from a template to get started</p>
            </div>
          ) : (
            workflows.map(wf => (
              <button key={wf.id} onClick={() => setSelectedWorkflow(wf)}
                className="w-full text-left bg-elevated border border-border rounded-lg px-3 py-2 hover:border-accent/30 transition-colors">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs font-medium text-text">{wf.name}</div>
                    <div className="text-[9px] text-text-muted truncate">{wf.description}</div>
                  </div>
                  <span className="text-[8px] text-text-muted">{wf.steps.length} steps</span>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
