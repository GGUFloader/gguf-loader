import { useEffect } from 'react'
import { useUIStore } from '../stores/uiStore'
import { useChatStore } from '../stores/chatStore'

export function useKeyboardShortcuts() {
  const { toggleAgentMode, toggleLeftPanel, toggleRightPanel } = useUIStore()
  const { isStreaming, stopStreaming } = useChatStore()

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't trigger shortcuts when typing in inputs
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        // Allow Escape even in inputs (to stop generation)
        if (e.key !== 'Escape') return
      }

      // Ctrl+M — Toggle agent mode
      if (e.ctrlKey && e.key === 'm') {
        e.preventDefault()
        toggleAgentMode()
      }

      // Ctrl+N — New chat
      if (e.ctrlKey && e.key === 'n') {
        e.preventDefault()
        // Trigger new chat via custom event
        window.dispatchEvent(new CustomEvent('shortcut:new-chat'))
      }

      // Ctrl+B — Toggle left panel
      if (e.ctrlKey && e.key === 'b') {
        e.preventDefault()
        toggleLeftPanel()
      }

      // Ctrl+\ — Toggle right panel
      if (e.ctrlKey && e.key === '\\') {
        e.preventDefault()
        toggleRightPanel()
      }

      // Ctrl+/ — Show shortcuts help
      if (e.ctrlKey && e.key === '/') {
        e.preventDefault()
        window.dispatchEvent(new CustomEvent('shortcut:show-help'))
      }

      // Ctrl+K — Focus search
      if (e.ctrlKey && e.key === 'k') {
        e.preventDefault()
        window.dispatchEvent(new CustomEvent('shortcut:focus-search'))
      }

      // Esc — Stop generation
      if (e.key === 'Escape' && isStreaming) {
        e.preventDefault()
        stopStreaming()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [toggleAgentMode, toggleLeftPanel, toggleRightPanel, isStreaming, stopStreaming])
}
