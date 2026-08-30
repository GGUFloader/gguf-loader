import { useState, useEffect, useRef, useCallback } from 'react'
import { FileText, Zap, Wrench, Brain } from 'lucide-react'
import { templatesApi, modelApi } from '../../api/client'

interface AutocompleteItem {
  id: string
  label: string
  description: string
  category: 'template' | 'file' | 'tool' | 'model' | 'command'
  icon: any
  insert: string // text to insert into input
}

interface ChatAutocompleteProps {
  query: string // current input text after trigger character
  trigger: string // '@' or '/' or '#'
  onSelect: (item: AutocompleteItem) => void
  onClose: () => void
}

const TOOL_NAMES = [
  'read_file', 'write_file', 'edit_file', 'list_directory',
  'search_files', 'run_command', 'git', 'glob', 'move_file',
  'remember', 'recall', 'forget', 'batch_execute',
  'generate_agents_md', 'export_session', 'record_correction',
  'python_interpreter',
]

const CATEGORY_INFO: Record<string, { icon: any; color: string }> = {
  template: { icon: FileText, color: 'text-blue-400' },
  file: { icon: FileText, color: 'text-green-400' },
  tool: { icon: Wrench, color: 'text-amber-400' },
  model: { icon: Brain, color: 'text-purple-400' },
  command: { icon: Zap, color: 'text-accent' },
}

export function ChatAutocomplete({ query, trigger, onSelect, onClose }: ChatAutocompleteProps) {
  const [items, setItems] = useState<AutocompleteItem[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  // Load items based on trigger
  const loadItems = useCallback(async () => {
    setLoading(true)
    const result: AutocompleteItem[] = []

    try {
      if (trigger === '@') {
        // Templates
        const templates = await templatesApi.list()
        for (const t of templates) {
          result.push({
            id: `template:${t.id}`,
            label: t.name,
            description: t.description,
            category: 'template',
            icon: FileText,
            insert: `@${t.id}`,
          })
        }
      } else if (trigger === '/') {
        // Tools
        for (const tool of TOOL_NAMES) {
          result.push({
            id: `tool:${tool}`,
            label: tool,
            description: `Use ${tool} tool`,
            category: 'tool',
            icon: Wrench,
            insert: `/${tool}`,
          })
        }
      } else if (trigger === '#') {
        // Models
        try {
          const catalog = await modelApi.catalog()
          for (const m of catalog.models || []) {
            result.push({
              id: `model:${m.path}`,
              label: m.filename,
              description: `${m.family || 'Unknown'} · ${m.size_human}`,
              category: 'model',
              icon: Brain,
              insert: `#${m.filename}`,
            })
          }
        } catch {}
      }
    } catch {}

    setItems(result)
    setSelectedIndex(0)
    setLoading(false)
  }, [trigger])

  useEffect(() => { loadItems() }, [loadItems])

  // Filter by query
  const filtered = query
    ? items.filter(i => i.label.toLowerCase().includes(query.toLowerCase()) ||
        i.description.toLowerCase().includes(query.toLowerCase()))
    : items

  // Keyboard navigation
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        if (filtered[selectedIndex]) {
          onSelect(filtered[selectedIndex])
        }
      } else if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }

    window.addEventListener('keydown', handleKey, true)
    return () => window.removeEventListener('keydown', handleKey, true)
  }, [filtered, selectedIndex, onSelect, onClose])

  // Scroll selected into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${selectedIndex}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  if (filtered.length === 0 && !loading) return null

  // Group by category
  const categories = [...new Set(filtered.map(i => i.category))]

  return (
    <div ref={listRef} className="absolute bottom-full left-0 right-0 mb-1 bg-surface border border-border rounded-lg shadow-xl max-h-60 overflow-y-auto z-50">
      {loading ? (
        <div className="px-3 py-2 text-xs text-text-muted">Loading...</div>
      ) : (
        categories.map(cat => {
          const catItems = filtered.filter(i => i.category === cat)
          const info = CATEGORY_INFO[cat]
          const Icon = info?.icon || Zap
          return (
            <div key={cat}>
              <div className="px-3 py-1 text-[9px] text-text-muted uppercase tracking-wider border-b border-border/50 flex items-center gap-1">
                <Icon size={9} className={info?.color || 'text-text-muted'} />
                {cat}
              </div>
              {catItems.map((item) => {
                const globalIdx = filtered.indexOf(item)
                return (
                  <button
                    key={item.id}
                    data-idx={globalIdx}
                    onClick={() => onSelect(item)}
                    onMouseEnter={() => setSelectedIndex(globalIdx)}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors ${
                      globalIdx === selectedIndex ? 'bg-accent/10' : 'hover:bg-elevated'
                    }`}
                  >
                    <Icon size={12} className={info?.color || 'text-text-muted'} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[11px] text-text truncate">{item.label}</div>
                      <div className="text-[9px] text-text-muted truncate">{item.description}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          )
        })
      )}
    </div>
  )
}

/**
 * Detect trigger character at the end of input text.
 * Returns { trigger, query } or null if no trigger.
 */
export function detectTrigger(text: string): { trigger: string; query: string } | null {
  // Match @, /, or # at start of word (after space or at beginning)
  const match = text.match(/(^|\s)([@/#])(\w*)$/)
  if (match) {
    return { trigger: match[2], query: match[3] }
  }
  return null
}
