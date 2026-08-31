import { create } from 'zustand'

export interface SidebarPlugin {
  id: string
  label: string
  icon: string
  category: 'core' | 'model' | 'agent' | 'dev' | 'collab'
  description: string
  enabled: boolean
  order: number
}

/** Agent tool toggle — matches backend TOOL_CATEGORIES */
export interface AgentTool {
  name: string
  label: string
  category: 'core' | 'dev' | 'agent'
  risk: 'low' | 'medium' | 'high'
  active: boolean
}

const STORAGE_KEY = 'ggufloader_sidebar_plugins'
const TOOLS_STORAGE_KEY = 'ggufloader_active_tools'

const DEFAULT_PLUGINS: SidebarPlugin[] = [
  // Core (always on)
  { id: 'files', label: 'Docs', icon: 'FileText', category: 'core', description: 'File explorer and document viewer', enabled: true, order: 0 },
  { id: 'dashboard', label: 'Dash', icon: 'LayoutDashboard', category: 'core', description: 'Workspace dashboard overview', enabled: true, order: 1 },
  { id: 'config', label: 'Config', icon: 'Sliders', category: 'core', description: 'Agent configuration and presets', enabled: true, order: 2 },
  { id: 'settings', label: 'Settings', icon: 'Settings', category: 'core', description: 'Application settings', enabled: true, order: 3 },

  // Model
  { id: 'catalog', label: 'Models', icon: 'Brain', category: 'model', description: 'Browse and search GGUF model catalog', enabled: false, order: 10 },
  { id: 'compare', label: 'Compare', icon: 'GitCompare', category: 'model', description: 'Compare model specs side by side', enabled: false, order: 11 },

  // Agent
  { id: 'templates', label: 'Prompts', icon: 'Copy', category: 'agent', description: 'Prompt templates and management', enabled: false, order: 20 },
  { id: 'diff', label: 'Diff', icon: 'FileCode', category: 'agent', description: 'File diff viewer for agent changes', enabled: false, order: 21 },
  { id: 'analytics', label: 'Stats', icon: 'BarChart3', category: 'agent', description: 'Agent performance analytics', enabled: false, order: 22 },
  { id: 'replay', label: 'Replay', icon: 'RotateCcw', category: 'agent', description: 'Session replay and debugging', enabled: false, order: 23 },
  { id: 'export', label: 'Export', icon: 'ArrowDownToLine', category: 'agent', description: 'Export and import sessions', enabled: false, order: 24 },
  { id: 'search', label: 'Search', icon: 'Search', category: 'agent', description: 'Advanced search across sessions', enabled: false, order: 25 },
  { id: 'workspace', label: 'Spaces', icon: 'FolderOpen', category: 'agent', description: 'Multi-workspace manager', enabled: false, order: 26 },
  { id: 'workflows', label: 'Flows', icon: 'GitBranch', category: 'agent', description: 'Workflow builder and pipelines', enabled: false, order: 27 },
  { id: 'canvas', label: 'Canvas', icon: 'GitBranch', category: 'agent', description: 'Visual workflow canvas editor', enabled: false, order: 28 },

  // Dev
  { id: 'profiling', label: 'Profile', icon: 'Activity', category: 'dev', description: 'Agent performance profiler', enabled: false, order: 30 },
  { id: 'plugins', label: 'Plugins', icon: 'Puzzle', category: 'dev', description: 'Plugin marketplace and management', enabled: false, order: 31 },
  { id: 'sandbox', label: 'Sandbox', icon: 'Shield', category: 'dev', description: 'WASM plugin sandbox', enabled: false, order: 32 },

  // Collab
  { id: 'collab', label: 'Collab', icon: 'Users', category: 'collab', description: 'Real-time collaboration', enabled: false, order: 40 },
  { id: 'benchmark', label: 'Bench', icon: 'Zap', category: 'collab', description: 'Model benchmarking', enabled: false, order: 41 },
  { id: 'benchchart', label: 'Charts', icon: 'LineChart', category: 'collab', description: 'Benchmark comparison charts', enabled: false, order: 42 },
]

/** Default agent tools — only 4 active out of the box */
const DEFAULT_ACTIVE_TOOLS: AgentTool[] = [
  // Core (always on)
  { name: 'read_file', label: 'Read File', category: 'core', risk: 'low', active: true },
  { name: 'list_directory', label: 'List Directory', category: 'core', risk: 'low', active: true },
  { name: 'search_files', label: 'Search Files', category: 'core', risk: 'low', active: true },
  { name: 'glob', label: 'Glob Find', category: 'core', risk: 'low', active: true },
  // Dev (disabled until user enables)
  { name: 'write_file', label: 'Write File', category: 'dev', risk: 'medium', active: false },
  { name: 'edit_file', label: 'Edit File', category: 'dev', risk: 'medium', active: false },
  { name: 'run_command', label: 'Run Command', category: 'dev', risk: 'high', active: false },
  { name: 'run_python', label: 'Run Python', category: 'dev', risk: 'high', active: false },
  { name: 'git', label: 'Git', category: 'dev', risk: 'high', active: false },
  { name: 'batch_execute', label: 'Batch Execute', category: 'dev', risk: 'medium', active: false },
  { name: 'python_interpreter', label: 'Python Sandbox', category: 'dev', risk: 'low', active: false },
  { name: 'move_file', label: 'Move File', category: 'dev', risk: 'medium', active: false },
  // Agent (disabled until user enables)
  { name: 'remember', label: 'Remember', category: 'agent', risk: 'low', active: false },
  { name: 'recall', label: 'Recall Memory', category: 'agent', risk: 'low', active: false },
  { name: 'forget', label: 'Forget Memory', category: 'agent', risk: 'low', active: false },
  { name: 'record_correction', label: 'Record Correction', category: 'agent', risk: 'low', active: false },
  { name: 'generate_agents_md', label: 'Generate AGENTS.md', category: 'agent', risk: 'low', active: false },
  { name: 'export_session', label: 'Export Session', category: 'agent', risk: 'low', active: false },
]

function loadToolState(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(TOOLS_STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return {}
}

function saveToolState(tools: AgentTool[]) {
  const map: Record<string, boolean> = {}
  for (const t of tools) map[t.name] = t.active
  localStorage.setItem(TOOLS_STORAGE_KEY, JSON.stringify(map))
}

function loadEnabled(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return {}
}

function saveEnabled(plugins: SidebarPlugin[]) {
  const map: Record<string, boolean> = {}
  for (const p of plugins) map[p.id] = p.enabled
  localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
}

interface PluginRegistryState {
  plugins: SidebarPlugin[]
  tools: AgentTool[]
  togglePlugin: (id: string) => void
  setPluginEnabled: (id: string, enabled: boolean) => void
  getEnabledPlugins: () => SidebarPlugin[]
  isCore: (id: string) => boolean
  toggleTool: (name: string) => void
  setToolActive: (name: string, active: boolean) => void
  getActiveTools: () => AgentTool[]
  getActiveToolNames: () => string[]
  isToolActive: (name: string) => boolean
}

function initPlugins(): SidebarPlugin[] {
  const saved = loadEnabled()
  return DEFAULT_PLUGINS.map((p) => ({
    ...p,
    enabled: p.category === 'core' ? true : (saved[p.id] ?? p.enabled),
  }))
}

function initTools(): AgentTool[] {
  const saved = loadToolState()
  return DEFAULT_ACTIVE_TOOLS.map((t) => ({
    ...t,
    // Core tools are always on
    active: t.category === 'core' ? true : (saved[t.name] ?? t.active),
  }))
}

export const usePluginRegistry = create<PluginRegistryState>((set, get) => ({
  plugins: initPlugins(),
  tools: initTools(),

  togglePlugin: (id) => {
    set((s) => {
      const plugins = s.plugins.map((p) =>
        p.id === id && p.category !== 'core' ? { ...p, enabled: !p.enabled } : p
      )
      saveEnabled(plugins)
      return { plugins }
    })
  },

  setPluginEnabled: (id, enabled) => {
    set((s) => {
      const plugins = s.plugins.map((p) =>
        p.id === id && p.category !== 'core' ? { ...p, enabled } : p
      )
      saveEnabled(plugins)
      return { plugins }
    })
  },

  getEnabledPlugins: () => get().plugins.filter((p) => p.enabled).sort((a, b) => a.order - b.order),

  isCore: (id) => get().plugins.find((p) => p.id === id)?.category === 'core',

  toggleTool: (name) => {
    set((s) => {
      const tool = s.tools.find((t) => t.name === name)
      if (!tool || tool.category === 'core') return s
      const tools = s.tools.map((t) =>
        t.name === name ? { ...t, active: !t.active } : t
      )
      saveToolState(tools)
      return { tools }
    })
  },

  setToolActive: (name, active) => {
    set((s) => {
      const tools = s.tools.map((t) =>
        t.name === name && t.category !== 'core' ? { ...t, active } : t
      )
      saveToolState(tools)
      return { tools }
    })
  },

  getActiveTools: () => get().tools.filter((t) => t.active),

  getActiveToolNames: () => get().tools.filter((t) => t.active).map((t) => t.name),

  isToolActive: (name) => get().tools.find((t) => t.name === name)?.active ?? false,
}))
