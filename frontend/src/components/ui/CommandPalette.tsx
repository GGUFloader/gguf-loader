import { useState, useEffect, useRef, useMemo } from 'react'
import { Command, ArrowRight, Zap, Brain, LayoutDashboard, Bot, FileText, Settings, RefreshCw, GitCompare } from 'lucide-react'
import { useShortcutsStore } from '../../stores/shortcutsStore'
import { useUIStore } from '../../stores/uiStore'
import { useChatStore } from '../../stores/chatStore'
import { useModelStore } from '../../stores/modelStore'


interface PaletteAction {
  id: string
  label: string
  description: string
  category: string
  icon: any
  action: () => void
  keywords: string[]
}

const CATEGORY_ORDER = ['Navigation', 'Model', 'Agent', 'View', 'Chat', 'System']

export function CommandPalette() {
  const { commandPaletteOpen, closeCommandPalette, shortcuts } = useShortcutsStore()
  const { setRightPanelTab, toggleAgentMode, toggleLeftPanel, toggleRightPanel, rightPanelOpen, leftPanelOpen, agentMode } = useUIStore()
  const { clearMessages } = useChatStore()
  const { info, unloadModel } = useModelStore()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Build action list from shortcuts + built-in actions
  const actions: PaletteAction[] = useMemo(() => {
    const builtIn: PaletteAction[] = [
      // Navigation
      { id: 'nav:files', label: 'Open Documents', description: 'Switch to file explorer', category: 'Navigation', icon: FileText, action: () => setRightPanelTab('files'), keywords: ['files', 'documents', 'explorer'] },
      { id: 'nav:dashboard', label: 'Open Dashboard', description: 'Workspace dashboard', category: 'Navigation', icon: LayoutDashboard, action: () => setRightPanelTab('dashboard'), keywords: ['dashboard', 'workspace', 'overview'] },
      { id: 'nav:templates', label: 'Open Templates', description: 'Prompt templates', category: 'Navigation', icon: FileText, action: () => setRightPanelTab('templates'), keywords: ['templates', 'prompts'] },
      { id: 'nav:diff', label: 'Open Diff Viewer', description: 'Code diff viewer', category: 'Navigation', icon: GitCompare, action: () => setRightPanelTab('diff'), keywords: ['diff', 'viewer', 'code'] },
      { id: 'nav:profiling', label: 'Open Profiling', description: 'Performance profiling', category: 'Navigation', icon: Zap, action: () => setRightPanelTab('profiling'), keywords: ['profiling', 'performance', 'metrics'] },
      { id: 'nav:plugins', label: 'Open Plugins', description: 'Plugin marketplace', category: 'Navigation', icon: Zap, action: () => setRightPanelTab('plugins'), keywords: ['plugins', 'marketplace', 'extensions'] },
      { id: 'nav:config', label: 'Open Agent Config', description: 'Configure agent presets and MCP', category: 'Navigation', icon: Settings, action: () => setRightPanelTab('config'), keywords: ['config', 'settings', 'agent', 'mcp'] },
      { id: 'nav:settings', label: 'Open Settings', description: 'Application settings', category: 'Navigation', icon: Settings, action: () => setRightPanelTab('settings'), keywords: ['settings', 'preferences'] },

      // Model
      { id: 'model:unload', label: 'Unload Model', description: 'Unload the current model', category: 'Model', icon: Brain, action: () => { unloadModel(); }, keywords: ['unload', 'model', 'free'] },
      { id: 'model:info', label: 'Show Model Info', description: 'Display current model info', category: 'Model', icon: Brain, action: () => {}, keywords: ['info', 'model', 'status'] },

      // Agent
      { id: 'agent:toggle', label: 'Toggle Agent Mode', description: agentMode ? 'Switch to chat mode' : 'Switch to agent mode', category: 'Agent', icon: Bot, action: () => { toggleAgentMode(); }, keywords: ['agent', 'toggle', 'mode', 'tools'] },

      // View
      { id: 'view:left', label: 'Toggle Left Panel', description: leftPanelOpen ? 'Hide sidebar' : 'Show sidebar', category: 'View', icon: LayoutDashboard, action: toggleLeftPanel, keywords: ['left', 'sidebar', 'panel'] },
      { id: 'view:right', label: 'Toggle Right Panel', description: rightPanelOpen ? 'Hide right panel' : 'Show right panel', category: 'View', icon: LayoutDashboard, action: toggleRightPanel, keywords: ['right', 'panel'] },

      // Chat
      { id: 'chat:clear', label: 'Clear Chat', description: 'Clear all messages', category: 'Chat', icon: FileText, action: () => { clearMessages(); }, keywords: ['clear', 'chat', 'messages'] },

      // System
      { id: 'system:refresh', label: 'Refresh Data', description: 'Refresh all data sources', category: 'System', icon: RefreshCw, action: () => {}, keywords: ['refresh', 'reload', 'update'] },
    ]

    // Add registered shortcuts
    const shortcutActions: PaletteAction[] = shortcuts
      .filter(s => !s.hidden)
      .map(s => ({
        id: `shortcut:${s.id}`,
        label: s.label,
        description: s.description,
        category: s.category,
        icon: Zap,
        action: s.action,
        keywords: [s.label.toLowerCase(), s.description.toLowerCase()],
      }))

    return [...builtIn, ...shortcutActions]
  }, [shortcuts, agentMode, leftPanelOpen, rightPanelOpen, info])

  // Filter by query
  const filtered = useMemo(() => {
    if (!query) return actions
    const q = query.toLowerCase()
    return actions.filter(a =>
      a.label.toLowerCase().includes(q) ||
      a.description.toLowerCase().includes(q) ||
      a.keywords.some(k => k.includes(q))
    ).sort((a, b) => {
      // Exact match first
      const aExact = a.label.toLowerCase().startsWith(q) ? 0 : 1
      const bExact = b.label.toLowerCase().startsWith(q) ? 0 : 1
      return aExact - bExact
    })
  }, [query, actions])

  // Group by category
  const grouped = useMemo(() => {
    const groups: Record<string, PaletteAction[]> = {}
    for (const a of filtered) {
      if (!groups[a.category]) groups[a.category] = []
      groups[a.category].push(a)
    }
    return CATEGORY_ORDER.filter(c => groups[c]).map(c => ({ category: c, items: groups[c] }))
  }, [filtered])

  // Reset on open
  useEffect(() => {
    if (commandPaletteOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [commandPaletteOpen])

  // Keyboard navigation
  useEffect(() => {
    if (!commandPaletteOpen) return

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (filtered[selectedIndex]) {
          filtered[selectedIndex].action()
          closeCommandPalette()
        }
      } else if (e.key === 'Escape') {
        e.preventDefault()
        closeCommandPalette()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [commandPaletteOpen, filtered, selectedIndex, closeCommandPalette])

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  if (!commandPaletteOpen) return null

  let flatIndex = -1

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={closeCommandPalette} />

      {/* Palette */}
      <div className="relative w-full max-w-lg bg-surface border border-border rounded-xl shadow-2xl overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <Command size={16} className="text-accent flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command..."
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0) }}
            className="flex-1 bg-transparent text-sm text-text placeholder-text-muted outline-none"
          />
          <kbd className="text-[10px] text-text-muted bg-elevated px-1.5 py-0.5 rounded border border-border">Esc</kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-80 overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-text-muted">
              No commands found for "{query}"
            </div>
          ) : (
            grouped.map(group => (
              <div key={group.category}>
                <div className="px-4 py-1.5 text-[10px] text-text-muted uppercase tracking-wider font-medium">
                  {group.category}
                </div>
                {group.items.map(action => {
                  flatIndex++
                  const idx = flatIndex
                  const Icon = action.icon
                  return (
                    <button
                      key={action.id}
                      data-index={idx}
                      onClick={() => { action.action(); closeCommandPalette() }}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className={`w-full flex items-center gap-3 px-4 py-2 text-left transition-colors ${
                        idx === selectedIndex ? 'bg-accent/10' : 'hover:bg-elevated'
                      }`}
                    >
                      <Icon size={14} className={idx === selectedIndex ? 'text-accent' : 'text-text-muted'} />
                      <div className="flex-1 min-w-0">
                        <div className={`text-xs ${idx === selectedIndex ? 'text-text' : 'text-text-sec'}`}>{action.label}</div>
                        <div className="text-[10px] text-text-muted truncate">{action.description}</div>
                      </div>
                      {idx === selectedIndex && <ArrowRight size={12} className="text-accent flex-shrink-0" />}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-border text-[10px] text-text-muted">
          <span>{filtered.length} commands</span>
          <div className="flex items-center gap-2">
            <span>↑↓ navigate</span>
            <span>↵ select</span>
            <span>esc close</span>
          </div>
        </div>
      </div>
    </div>
  )
}
