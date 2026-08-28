import { create } from 'zustand'

interface UIState {
  theme: 'dark' | 'light'
  leftPanelOpen: boolean
  rightPanelOpen: boolean
  rightPanelTab: string
  agentMode: boolean
  toggleTheme: () => void
  toggleLeftPanel: () => void
  toggleRightPanel: () => void
  setRightPanelTab: (tab: string) => void
  toggleAgentMode: () => void
}

export const useUIStore = create<UIState>((set) => ({
  theme: 'dark',
  leftPanelOpen: true,
  rightPanelOpen: true,
  rightPanelTab: 'files',
  agentMode: true,

  toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
  toggleLeftPanel: () => set((s) => ({ leftPanelOpen: !s.leftPanelOpen })),
  toggleRightPanel: () => set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
  setRightPanelTab: (tab) => set({ rightPanelTab: tab }),
  toggleAgentMode: () => set((s) => ({ agentMode: !s.agentMode })),
}))
