import { create } from 'zustand'

export interface Shortcut {
  id: string
  label: string
  description: string
  category: string
  keys: string[] // e.g. ['Cmd', 'K'] or ['Ctrl', 'Shift', 'A']
  action: () => void
  icon?: string
  hidden?: boolean // don't show in command palette
}

interface ShortcutsState {
  shortcuts: Shortcut[]
  commandPaletteOpen: boolean
  register: (shortcut: Omit<Shortcut, 'action'> & { action: () => void }) => void
  unregister: (id: string) => void
  toggleCommandPalette: () => void
  openCommandPalette: () => void
  closeCommandPalette: () => void
  getByCategory: (category: string) => Shortcut[]
}

export const useShortcutsStore = create<ShortcutsState>((set, get) => ({
  shortcuts: [],
  commandPaletteOpen: false,

  register: (shortcut) => {
    set((s) => {
      // Replace if same id exists
      const existing = s.shortcuts.findIndex(sc => sc.id === shortcut.id)
      const list = [...s.shortcuts]
      if (existing >= 0) {
        list[existing] = shortcut as Shortcut
      } else {
        list.push(shortcut as Shortcut)
      }
      return { shortcuts: list }
    })
  },

  unregister: (id) => {
    set((s) => ({ shortcuts: s.shortcuts.filter(sc => sc.id !== id) }))
  },

  toggleCommandPalette: () => set((s) => ({ commandPaletteOpen: !s.commandPaletteOpen })),
  openCommandPalette: () => set({ commandPaletteOpen: true }),
  closeCommandPalette: () => set({ commandPaletteOpen: false }),

  getByCategory: (category) => get().shortcuts.filter(s => s.category === category),
}))

// Format shortcut keys for display
export function formatKeys(keys: string[]): string {
  const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
  return keys.map(k => {
    if (k === 'Cmd') return isMac ? '⌘' : 'Ctrl'
    if (k === 'Ctrl') return isMac ? '⌃' : 'Ctrl'
    if (k === 'Shift') return isMac ? '⇧' : 'Shift'
    if (k === 'Alt') return isMac ? '⌥' : 'Alt'
    if (k === 'Enter') return '↵'
    if (k === 'Escape') return 'Esc'
    if (k === ' ') return 'Space'
    return k
  }).join(isMac ? '' : '+')
}

// Normalize keyboard event to shortcut key string
export function eventToKey(e: KeyboardEvent): string {
  if (e.key === 'Meta') return 'Cmd'
  if (e.key === 'Control') return 'Ctrl'
  if (e.key === 'Shift') return 'Shift'
  if (e.key === 'Alt') return 'Alt'
  return e.key.length === 1 ? e.key.toUpperCase() : e.key
}
