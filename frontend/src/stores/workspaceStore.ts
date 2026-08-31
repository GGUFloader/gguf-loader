import { create } from 'zustand'

function loadWorkspace(): string {
  try {
    const saved = localStorage.getItem('ggufloader_settings')
    if (saved) {
      const s = JSON.parse(saved)
      if (s.workspace) return s.workspace
    }
  } catch {}
  return '.'
}

interface WorkspaceState {
  workspace: string
  setWorkspace: (path: string) => void
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  workspace: loadWorkspace(),
  setWorkspace: (path: string) => {
    // Persist to localStorage
    try {
      const saved = localStorage.getItem('ggufloader_settings')
      const settings = saved ? JSON.parse(saved) : {}
      settings.workspace = path
      localStorage.setItem('ggufloader_settings', JSON.stringify(settings))
    } catch {}
    set({ workspace: path })
  },
}))
