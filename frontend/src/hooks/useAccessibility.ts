import { useEffect, useRef, useCallback } from 'react'

/**
 * Manage focus for route/panel changes.
 * Returns a ref to attach to the main content area.
 */
export function useFocusTrap(enabled: boolean = false) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (enabled && ref.current) {
      ref.current.focus()
    }
  }, [enabled])

  return ref
}

/**
 * Announce messages to screen readers via ARIA live region.
 */
export function useAnnounce() {
  const announce = useCallback((message: string, priority: 'polite' | 'assertive' = 'polite') => {
    const el = document.getElementById(`aria-live-${priority}`)
    if (el) {
      el.textContent = message
      // Clear after a delay so repeated identical messages re-trigger
      setTimeout(() => { el.textContent = '' }, 1000)
    }
  }, [])

  return announce
}

/**
 * Manage focus restoration when panels open/close.
 */
export function useFocusRestore() {
  const previousFocus = useRef<HTMLElement | null>(null)

  const save = useCallback(() => {
    previousFocus.current = document.activeElement as HTMLElement
  }, [])

  const restore = useCallback(() => {
    if (previousFocus.current && previousFocus.current.focus) {
      previousFocus.current.focus()
    }
  }, [])

  return { save, restore }
}

/**
 * Global keyboard shortcuts for accessibility:
 * - Skip to main content (Alt+1)
 * - Skip to chat input (Alt+2)
 * - Focus command palette (already handled by shortcuts store)
 */
export function useAccessibilityShortcuts() {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.altKey && e.key === '1') {
        e.preventDefault()
        const main = document.getElementById('main-content')
        if (main) {
          main.tabIndex = -1
          main.focus()
        }
      }
      if (e.altKey && e.key === '2') {
        e.preventDefault()
        const input = document.querySelector<HTMLTextAreaElement>('[data-chat-input]')
        if (input) input.focus()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])
}
