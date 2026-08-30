import { useState, useEffect } from 'react'
import { Bot, Zap, ChevronDown, Search, FileText, RefreshCw, Bug, Rocket } from 'lucide-react'
import { useUIStore } from '../../stores/uiStore'
import { agentApi } from '../../api/client'

interface AgentPreset {
  id: string
  name: string
  description: string
  icon: string
  max_steps: number
  temperature: number
}

const ICON_MAP: Record<string, typeof Bot> = {
  '🔍': Search,
  '📝': FileText,
  '♻️': RefreshCw,
  '🐛': Bug,
  '🚀': Rocket,
  '⚡': Zap,
}

const FALLBACK_PRESETS: AgentPreset[] = [
  { id: 'research', name: 'Research', description: 'Read-only exploration. No file modifications.', icon: '🔍', max_steps: 12, temperature: 0.1 },
  { id: 'code_review', name: 'Code Review', description: 'Structured code analysis with actionable feedback.', icon: '📝', max_steps: 10, temperature: 0.1 },
  { id: 'refactor', name: 'Refactor', description: 'Safe code refactoring with automatic verification.', icon: '♻️', max_steps: 15, temperature: 0.05 },
  { id: 'debug', name: 'Debug', description: 'Error-focused debugging with diagnostics.', icon: '🐛', max_steps: 12, temperature: 0.1 },
  { id: 'full_stack', name: 'Full Stack', description: 'All tools enabled. Maximum flexibility.', icon: '🚀', max_steps: 20, temperature: 0.1 },
  { id: 'quick_fix', name: 'Quick Fix', description: 'Fast, minimal changes. Few steps, no fluff.', icon: '⚡', max_steps: 4, temperature: 0.05 },
]

export function ModeSelector() {
  const [isOpen, setIsOpen] = useState(false)
  const [presets, setPresets] = useState<AgentPreset[]>(FALLBACK_PRESETS)
  const { agentMode, toggleAgentMode } = useUIStore()

  // Load presets from backend
  useEffect(() => {
    agentApi.presets().then((data) => {
      if (data && data.length > 0) setPresets(data)
    }).catch(() => {})
  }, [])

  // Get current preset from localStorage
  const [currentPreset, setCurrentPreset] = useState('full_stack')
  useEffect(() => {
    try {
      const saved = localStorage.getItem('ggufloader_settings')
      if (saved) {
        const s = JSON.parse(saved)
        if (s.preset) setCurrentPreset(s.preset)
      }
    } catch {}
  }, [])

  function handleSelect(presetId: string) {
    // Save to localStorage
    try {
      const saved = localStorage.getItem('ggufloader_settings')
      const settings = saved ? JSON.parse(saved) : {}
      settings.preset = presetId
      localStorage.setItem('ggufloader_settings', JSON.stringify(settings))
    } catch {}
    setCurrentPreset(presetId)

    // Enable agent mode if selecting a non-default preset
    if (!agentMode) toggleAgentMode()
    setIsOpen(false)
  }

  const activePreset = presets.find(p => p.id === currentPreset) || presets[0]
  const Icon = ICON_MAP[activePreset.icon] || Bot

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 bg-elevated border border-border rounded-lg text-sm text-text hover:bg-elevated/80 transition-colors"
      >
        <Icon size={14} className="text-accent" />
        <span>{activePreset.name}</span>
        <ChevronDown size={12} className="text-text-muted" />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute top-full left-0 mt-1 w-64 bg-elevated border border-border rounded-xl shadow-xl z-50 overflow-hidden">
            <div className="px-3 py-2 border-b border-border">
              <div className="text-xs font-medium text-text-muted">Agent Preset</div>
            </div>
            {presets.map((preset) => {
              const PresetIcon = ICON_MAP[preset.icon] || Bot
              const isActive = preset.id === currentPreset
              return (
                <button
                  key={preset.id}
                  onClick={() => handleSelect(preset.id)}
                  className={`w-full flex items-start gap-3 px-3 py-2.5 text-left transition-colors ${
                    isActive
                      ? 'bg-accent/10 text-accent'
                      : 'text-text hover:bg-elevated/80'
                  }`}
                >
                  <PresetIcon size={16} className="mt-0.5 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{preset.name}</div>
                    <div className="text-xs text-text-muted leading-relaxed">{preset.description}</div>
                    <div className="text-[10px] text-text-muted mt-0.5">
                      {preset.max_steps} steps · temp {preset.temperature}
                    </div>
                  </div>
                  {isActive && (
                    <div className="w-2 h-2 rounded-full bg-accent mt-1.5 flex-shrink-0" />
                  )}
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
