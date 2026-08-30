import { MessageSquare, FolderOpen, Brain, Settings, Bot } from 'lucide-react'
import { useUIStore } from '../../stores/uiStore'

interface NavItem {
  id: string
  label: string
  icon: any
  action: () => void
}

export function MobileNav() {
  const { setRightPanelTab, rightPanelTab, agentMode, toggleAgentMode } = useUIStore()

  const items: NavItem[] = [
    { id: 'chat', label: 'Chat', icon: MessageSquare, action: () => setRightPanelTab('files') },
    { id: 'models', label: 'Models', icon: Brain, action: () => setRightPanelTab('catalog') },
    { id: 'agent', label: 'Agent', icon: Bot, action: () => toggleAgentMode() },
    { id: 'files', label: 'Files', icon: FolderOpen, action: () => setRightPanelTab('files') },
    { id: 'settings', label: 'More', icon: Settings, action: () => setRightPanelTab('settings') },
  ]

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-surface border-t border-border z-40 safe-area-bottom" role="navigation" aria-label="Main navigation">
      <div className="flex items-center justify-around h-14">
        {items.map(item => {
          const Icon = item.icon
          const isActive = item.id === 'agent' ? agentMode : rightPanelTab === item.id
          return (
            <button
              key={item.id}
              onClick={item.action}
              className={`flex flex-col items-center justify-center gap-0.5 flex-1 h-full transition-colors ${
                isActive ? 'text-accent' : 'text-text-muted'
              }`}
              aria-label={item.label}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon size={20} />
              <span className="text-[10px]">{item.label}</span>
              {isActive && <div className="w-4 h-0.5 bg-accent rounded-full mt-0.5" />}
            </button>
          )
        })}
      </div>
    </nav>
  )
}
