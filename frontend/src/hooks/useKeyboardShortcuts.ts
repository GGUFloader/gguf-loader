import { useEffect } from 'react'
import { useShortcutsStore, eventToKey } from '../stores/shortcutsStore'
import { useUIStore } from '../stores/uiStore'
import { useChatStore } from '../stores/chatStore'

/**
 * Global keyboard shortcuts listener.
 * Registers default shortcuts and listens for keydown events.
 */
export function useKeyboardShortcuts() {
  const { register, shortcuts, toggleCommandPalette } = useShortcutsStore()
  const { setRightPanelTab, toggleAgentMode, toggleLeftPanel, toggleRightPanel } = useUIStore()
  const { clearMessages } = useChatStore()

  // Register default shortcuts on mount
  useEffect(() => {
    const defaults = [
      { id: 'cmd+k', label: 'Command Palette', description: 'Open command palette', category: 'System', keys: ['Cmd', 'K'], action: toggleCommandPalette },
      { id: 'ctrl+k', label: 'Command Palette', description: 'Open command palette', category: 'System', keys: ['Ctrl', 'K'], action: toggleCommandPalette, hidden: true },
      { id: 'toggle-agent', label: 'Toggle Agent Mode', description: 'Switch between chat and agent mode', category: 'Agent', keys: ['Cmd', 'Shift', 'A'], action: toggleAgentMode },
      { id: 'clear-chat', label: 'Clear Chat', description: 'Clear all messages', category: 'Chat', keys: ['Cmd', 'Shift', 'L'], action: clearMessages },
      { id: 'toggle-left', label: 'Toggle Left Panel', description: 'Show/hide left sidebar', category: 'View', keys: ['Cmd', 'Shift', '['], action: toggleLeftPanel },
      { id: 'toggle-right', label: 'Toggle Right Panel', description: 'Show/hide right panel', category: 'View', keys: ['Cmd', 'Shift', ']'], action: toggleRightPanel },
      { id: 'panel-files', label: 'Open Files', description: 'Switch to file explorer', category: 'Navigation', keys: ['Cmd', '1'], action: () => setRightPanelTab('files') },
      { id: 'panel-dash', label: 'Open Dashboard', description: 'Switch to dashboard', category: 'Navigation', keys: ['Cmd', '2'], action: () => setRightPanelTab('dashboard') },
      { id: 'panel-models', label: 'Open Models', description: 'Switch to model catalog', category: 'Navigation', keys: ['Cmd', '3'], action: () => setRightPanelTab('catalog') },
      { id: 'panel-templates', label: 'Open Templates', description: 'Switch to templates', category: 'Navigation', keys: ['Cmd', '4'], action: () => setRightPanelTab('templates') },
    ]

    for (const s of defaults) {
      register(s)
    }
  }, []) // register only once

  // Listen for keydown events
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const pressed: string[] = []
      if (e.metaKey || e.ctrlKey) pressed.push('Cmd')
      if (e.shiftKey) pressed.push('Shift')
      if (e.altKey) pressed.push('Alt')
      pressed.push(eventToKey(e))

      // Check against registered shortcuts
      for (const shortcut of shortcuts) {
        if (shortcut.keys.length !== pressed.length) continue
        const match = shortcut.keys.every((k, i) => {
          const p = pressed[i]
          return k === p || (k === 'Cmd' && (p === 'Cmd' || p === 'Ctrl'))
        })
        if (match) {
          e.preventDefault()
          e.stopPropagation()
          shortcut.action()
          return
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown, true)
    return () => window.removeEventListener('keydown', handleKeyDown, true)
  }, [shortcuts])
}
