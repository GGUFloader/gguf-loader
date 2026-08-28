import { useState } from 'react'
import { Bot, Terminal, Zap, Palette, ChevronDown } from 'lucide-react'
import { useUIStore } from '../../stores/uiStore'

const MODES = [
  {
    id: 'standard',
    label: 'Standard',
    icon: Bot,
    description: 'Chat mode with optional tools',
  },
  {
    id: 'agent',
    label: 'Agent',
    icon: Terminal,
    description: 'Full agent with file & shell access',
  },
  {
    id: 'minimal',
    label: 'Minimal',
    icon: Zap,
    description: 'Fast responses, no tools',
  },
  {
    id: 'creator',
    label: 'Creator',
    icon: Palette,
    description: 'Creative mode, relaxed guardrails',
  },
]

export function ModeSelector() {
  const [isOpen, setIsOpen] = useState(false)
  const { agentMode, toggleAgentMode } = useUIStore()
  const currentMode = agentMode ? 'agent' : 'standard'
  const current = MODES.find((m) => m.id === currentMode)!
  const Icon = current.icon

  function handleSelect(modeId: string) {
    if (modeId === 'agent' && !agentMode) {
      toggleAgentMode()
    } else if (modeId !== 'agent' && agentMode) {
      toggleAgentMode()
    }
    setIsOpen(false)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 bg-elevated border border-border rounded-lg text-sm text-text hover:bg-elevated/80 transition-colors"
      >
        <Icon size={14} className="text-accent" />
        <span>{current.label}</span>
        <ChevronDown size={12} className="text-text-muted" />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute top-full left-0 mt-1 w-56 bg-elevated border border-border rounded-xl shadow-xl z-50 overflow-hidden">
            <div className="px-3 py-2 border-b border-border">
              <div className="text-xs font-medium text-text-muted">Select Mode</div>
            </div>
            {MODES.map((mode) => {
              const ModeIcon = mode.icon
              const isActive = mode.id === currentMode
              return (
                <button
                  key={mode.id}
                  onClick={() => handleSelect(mode.id)}
                  className={`w-full flex items-start gap-3 px-3 py-2.5 text-left transition-colors ${
                    isActive
                      ? 'bg-accent/10 text-accent'
                      : 'text-text hover:bg-elevated/80'
                  }`}
                >
                  <ModeIcon size={16} className="mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="text-sm font-medium">{mode.label}</div>
                    <div className="text-xs text-text-muted">{mode.description}</div>
                  </div>
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
