import { useState } from 'react'
import { useUIStore } from '../../stores/uiStore'
import { usePluginRegistry } from '../../stores/pluginRegistry'
import { FileExplorer } from '../workbench/FileExplorer'
import { FileViewer } from '../workbench/FileViewer'
import { SettingsDialog } from '../settings/SettingsDialog'
import { SessionReplayPanel } from '../agent/SessionReplayPanel'
import { WorkspaceDashboard } from '../agent/WorkspaceDashboard'
import { ProfilingPanel } from '../agent/ProfilingPanel'
import { AgentConfigPanel } from '../agent/AgentConfigPanel'
import { PluginMarketplacePanel } from '../agent/PluginMarketplacePanel'
import { TemplatePanel } from '../agent/TemplatePanel'
import { DiffViewerPanel } from '../agent/DiffViewerPanel'
import { AnalyticsDashboard } from '../agent/AnalyticsDashboard'
import { ExportImportPanel } from '../agent/ExportImportPanel'
import { AdvancedSearchPanel } from '../agent/AdvancedSearchPanel'
import { WorkspaceManagerPanel } from '../agent/WorkspaceManagerPanel'
import { WorkflowBuilderPanel } from '../agent/WorkflowBuilderPanel'
import { WorkflowCanvas } from '../agent/WorkflowCanvas'
import { BenchmarkPanel } from '../agent/BenchmarkPanel'
import { BenchmarkChartPanel } from '../agent/BenchmarkChartPanel'
import { CollabPanel } from '../agent/CollabPanel'
import { PluginSandboxPanel } from '../agent/PluginSandboxPanel'
import { ArtifactsSection } from '../chat/ArtifactsSection'
import { ContextSection } from '../chat/ContextSection'
import {
  FileText, Settings, RotateCcw, LayoutDashboard, Activity, Brain, Sliders, GitCompare,
  Puzzle, Copy, FileCode, BarChart3, ArrowDownToLine, Search, FolderOpen, GitBranch,
  Zap, Users, LineChart, Shield,
} from 'lucide-react'

// Map icon names to actual components
const ICON_MAP: Record<string, typeof FileText> = {
  FileText, Settings, RotateCcw, LayoutDashboard, Activity, Brain, Sliders, GitCompare,
  Puzzle, Copy, FileCode, BarChart3, ArrowDownToLine, Search, FolderOpen, GitBranch,
  Zap, Users, LineChart, Shield,
}

// Map plugin IDs to components
const COMPONENT_MAP: Record<string, React.ComponentType<any>> = {
  files: FileExplorer,
  dashboard: WorkspaceDashboard,
  config: AgentConfigPanel,
  settings: SettingsDialog,
  templates: TemplatePanel,
  diff: DiffViewerPanel,
  analytics: AnalyticsDashboard,
  export: ExportImportPanel,
  search: AdvancedSearchPanel,
  workspace: WorkspaceManagerPanel,
  workflows: WorkflowBuilderPanel,
  canvas: WorkflowCanvas,
  profiling: ProfilingPanel,
  plugins: PluginMarketplacePanel,
  sandbox: PluginSandboxPanel,
  collab: CollabPanel,
  benchmark: BenchmarkPanel,
  benchchart: BenchmarkChartPanel,
  replay: SessionReplayPanel,
}

export function RightPanel() {
  const { rightPanelTab, setRightPanelTab } = useUIStore()
  const { getEnabledPlugins } = usePluginRegistry()
  const [selectedFile, setSelectedFile] = useState<string | null>(null)

  const enabledPlugins = getEnabledPlugins()

  function handleFileSelect(path: string) {
    setSelectedFile(path)
  }

  function handleTabClick(id: string) {
    setRightPanelTab(id)
    if (id === 'files') setSelectedFile(null)
  }

  // Render the active tab content
  function renderContent() {
    const tab = rightPanelTab

    // Special handling for files tab (file viewer)
    if (tab === 'files' && selectedFile) {
      return <FileViewer filePath={selectedFile} onClose={() => setSelectedFile(null)} />
    }

    // Special handling for settings tab
    if (tab === 'settings') {
      return <SettingsDialog onClose={() => setRightPanelTab('files')} />
    }

    // Look up component from map
    const Component = COMPONENT_MAP[tab]
    if (Component) {
      if (tab === 'files') {
        return <FileExplorer onFileSelect={handleFileSelect} selectedFile={selectedFile} />
      }
      return <Component />
    }

    return null
  }

  return (
    <aside className="w-80 h-full flex flex-col bg-surface border-l border-border" aria-label="Right panel">
      {/* Collapsible sections — always visible at top */}
      <div className="border-b border-border">
        <ArtifactsSection />
        <ContextSection />
      </div>

      {/* Plugin tabs — scrollable */}
      <div className="flex border-b border-border overflow-x-auto" role="tablist" aria-label="Panel tabs">
        {enabledPlugins.map((plugin) => {
          const Icon = ICON_MAP[plugin.icon] || FileText
          const active = rightPanelTab === plugin.id
          return (
            <button
              key={plugin.id}
              onClick={() => handleTabClick(plugin.id)}
              role="tab"
              aria-selected={active}
              aria-controls={`panel-${plugin.id}`}
              title={plugin.description}
              className={`flex-shrink-0 flex items-center justify-center gap-1 px-2.5 py-2.5 text-[11px] font-medium transition-colors relative ${
                active
                  ? 'text-accent border-b-2 border-accent'
                  : 'text-text-muted hover:text-text-sec'
              }`}
            >
              <Icon size={13} />
              <span className="hidden lg:inline">{plugin.label}</span>
            </button>
          )
        })}

        {/* Gear icon for plugin settings */}
        <button
          onClick={() => handleTabClick('settings')}
          title="Plugin Settings"
          className="flex-shrink-0 flex items-center justify-center px-2.5 py-2.5 text-text-muted hover:text-text-sec transition-colors ml-auto border-l border-border"
        >
          <Settings size={13} />
        </button>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {renderContent()}
      </div>
    </aside>
  )
}
