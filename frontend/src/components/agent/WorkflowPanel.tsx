import { useState, useEffect } from 'react'
import { Play, Plus, GitBranch, RefreshCw } from 'lucide-react'
import { workflowsApi } from '../../api/client'

interface Workflow {
  id: string
  name: string
  description: string
  status: string
}

interface WorkflowTemplate {
  id: string
  name: string
  description: string
}

export function WorkflowPanel() {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [showTemplates, setShowTemplates] = useState(false)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [w, t] = await Promise.all([workflowsApi.list(), workflowsApi.templates()])
      setWorkflows(w)
      setTemplates(t)
    } catch {}
    setLoading(false)
  }

  async function handleCreateFromTemplate(template: WorkflowTemplate) {
    await workflowsApi.create(template.name, template.description)
    setShowTemplates(false)
    loadData()
  }

  async function handleRun(id: string) {
    await workflowsApi.run(id)
  }

  return (
    <div className="h-full flex flex-col p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <GitBranch size={14} className="text-accent" />
          Workflows
        </h3>
        <div className="flex gap-1">
          <button onClick={loadData} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
            <RefreshCw size={13} />
          </button>
          <button onClick={() => setShowTemplates(!showTemplates)} className="p-1.5 text-text-muted hover:text-accent rounded hover:bg-elevated transition-colors">
            <Plus size={13} />
          </button>
        </div>
      </div>

      {showTemplates && (
        <div className="bg-elevated border border-border rounded-lg p-3 space-y-2 animate-slide-up">
          <div className="text-xs text-text-muted font-medium mb-1">Create from template</div>
          {templates.map(t => (
            <button key={t.id} onClick={() => handleCreateFromTemplate(t)}
              className="w-full text-left px-3 py-2 rounded-lg bg-bg border border-border hover:border-accent/30 transition-colors">
              <div className="text-xs text-text font-medium">{t.name}</div>
              <div className="text-[10px] text-text-muted">{t.description}</div>
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="text-xs text-text-muted">Loading...</div>
      ) : workflows.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-xs">
          <GitBranch size={24} className="mx-auto mb-2 opacity-30" />
          <p>No workflows yet</p>
          <p className="mt-1 text-text-muted/50">Create from a template to get started</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-2">
          {workflows.map(wf => (
            <div key={wf.id} className="bg-elevated border border-border rounded-lg p-3 flex items-center justify-between">
              <div className="min-w-0">
                <div className="text-xs font-medium text-text">{wf.name}</div>
                <div className="text-[10px] text-text-muted">{wf.description || 'No description'}</div>
              </div>
              <button onClick={() => handleRun(wf.id)} className="p-1.5 text-accent hover:bg-accent/10 rounded transition-colors" title="Run">
                <Play size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
