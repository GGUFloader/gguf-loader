import { useState, useEffect } from 'react'
import { FileText, Search, Play, RefreshCw, ChevronDown, ChevronRight, Copy } from 'lucide-react'
import { templatesApi } from '../../api/client'

interface Template {
  id: string
  name: string
  description: string
  template: string
  variables: string[]
  category: string
  tags: string[]
  builtin: boolean
}

interface Category {
  name: string
  count: number
}

export function TemplatePanel() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [expandedTemplate, setExpandedTemplate] = useState<string | null>(null)
  const [renderedOutput, setRenderedOutput] = useState<string>('')
  const [renderingTemplate, setRenderingTemplate] = useState<string | null>(null)
  const [variableValues, setVariableValues] = useState<Record<string, string>>({})
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [t, c] = await Promise.all([templatesApi.list(), templatesApi.categories()])
      setTemplates(t)
      setCategories(c)
    } catch {}
    setLoading(false)
  }

  async function handleRender(template: Template) {
    setRenderingTemplate(template.id)
    const vars: Record<string, string> = {}
    template.variables.forEach(v => { vars[v] = variableValues[v] || `[${v}]` })
    try {
      const result = await templatesApi.render(template.id, vars)
      setRenderedOutput(result.rendered)
    } catch {}
    setRenderingTemplate(null)
  }

  function handleCopy(text: string, id: string) {
    navigator.clipboard.writeText(text).catch(() => {})
    setCopied(id)
    setTimeout(() => setCopied(null), 1500)
  }

  const filtered = templates
    .filter(t => !activeCategory || t.category === activeCategory)
    .filter(t => !search || t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase()) ||
      t.tags.some(tag => tag.toLowerCase().includes(search.toLowerCase())))

  return (
    <div className="h-full flex flex-col p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <FileText size={14} className="text-accent" />
          Templates
        </h3>
        <button onClick={loadData} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Search */}
      <div className="flex items-center gap-2 px-2 py-1.5 bg-elevated border border-border rounded-lg">
        <Search size={14} className="text-text-muted" />
        <input type="text" placeholder="Search templates..." value={search} onChange={e => setSearch(e.target.value)}
          className="bg-transparent text-sm text-text placeholder-text-muted outline-none w-full" />
      </div>

      {/* Categories */}
      {categories.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <button onClick={() => setActiveCategory(null)}
            className={`text-[10px] px-2 py-1 rounded-full border transition-colors ${!activeCategory ? 'bg-accent/15 text-accent border-accent/30' : 'text-text-muted border-border hover:border-accent/30'}`}>
            All
          </button>
          {categories.map(cat => (
            <button key={cat.name} onClick={() => setActiveCategory(activeCategory === cat.name ? null : cat.name)}
              className={`text-[10px] px-2 py-1 rounded-full border transition-colors ${activeCategory === cat.name ? 'bg-accent/15 text-accent border-accent/30' : 'text-text-muted border-border hover:border-accent/30'}`}>
              {cat.name} ({cat.count})
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Loading templates...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-xs">
          <FileText size={24} className="mx-auto mb-2 opacity-30" />
          <p>No templates found</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-1.5">
          {filtered.map(t => (
            <div key={t.id} className={`bg-elevated border rounded-lg transition-all ${expandedTemplate === t.id ? 'border-accent/50' : 'border-border hover:border-accent/30'}`}>
              <button onClick={() => { setExpandedTemplate(expandedTemplate === t.id ? null : t.id); setRenderedOutput('') }}
                className="w-full text-left px-3 py-2">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium text-text">{t.name}</div>
                    <div className="text-[9px] text-text-muted truncate">{t.description}</div>
                  </div>
                  <div className="flex items-center gap-1.5 ml-2">
                    {t.builtin && <span className="text-[8px] px-1 py-0.5 bg-accent/10 text-accent rounded">builtin</span>}
                    {t.variables.length > 0 && <span className="text-[8px] text-text-muted">{t.variables.length} vars</span>}
                    {expandedTemplate === t.id ? <ChevronDown size={12} className="text-text-muted" /> : <ChevronRight size={12} className="text-text-muted" />}
                  </div>
                </div>
              </button>

              {expandedTemplate === t.id && (
                <div className="px-3 pb-3 space-y-2 border-t border-border/50">
                  {/* Tags */}
                  {t.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {t.tags.map(tag => (
                        <span key={tag} className="text-[8px] px-1.5 py-0.5 bg-bg rounded text-text-muted">{tag}</span>
                      ))}
                    </div>
                  )}

                  {/* Template preview */}
                  <div className="bg-bg rounded-lg px-3 py-2 text-[10px] text-text-sec font-mono whitespace-pre-wrap max-h-32 overflow-y-auto">
                    {t.template}
                  </div>

                  {/* Variables */}
                  {t.variables.length > 0 && (
                    <div className="space-y-1">
                      <div className="text-[9px] text-text-muted uppercase">Variables</div>
                      {t.variables.map(v => (
                        <input key={v} placeholder={v} value={variableValues[v] || ''}
                          onChange={e => setVariableValues({ ...variableValues, [v]: e.target.value })}
                          className="w-full bg-bg border border-border rounded px-2 py-1 text-[10px] text-text outline-none focus:border-accent" />
                      ))}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2">
                    <button onClick={() => handleRender(t)} disabled={renderingTemplate === t.id}
                      className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-accent text-onAccent rounded-lg text-[10px] font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors">
                      <Play size={10} /> {renderingTemplate === t.id ? 'Rendering...' : 'Render'}
                    </button>
                    <button onClick={() => handleCopy(t.template, t.id)}
                      className="flex items-center justify-center gap-1 px-2 py-1.5 bg-elevated border border-border rounded-lg text-[10px] text-text-sec hover:border-accent/30 transition-colors">
                      {copied === t.id ? '✓' : <><Copy size={10} /> Copy</>}
                    </button>
                  </div>

                  {/* Rendered output */}
                  {renderedOutput && renderingTemplate === null && expandedTemplate === t.id && (
                    <div className="bg-green-500/5 border border-green-500/20 rounded-lg px-3 py-2">
                      <div className="text-[9px] text-green-400 uppercase mb-1">Rendered</div>
                      <div className="text-[10px] text-text-sec font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">{renderedOutput}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
