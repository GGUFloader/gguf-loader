import { useState } from 'react'
import { useUIStore } from '../../stores/uiStore'
import { FileExplorer } from '../workbench/FileExplorer'
import { FileViewer } from '../workbench/FileViewer'
import { SettingsDialog } from '../settings/SettingsDialog'
import { SessionReplayPanel } from '../agent/SessionReplayPanel'
import { WorkspaceDashboard } from '../agent/WorkspaceDashboard'
import { ProfilingPanel } from '../agent/ProfilingPanel'
import { ModelCatalogPanel } from '../model/ModelCatalogPanel'
import { ModelComparePanel } from '../model/ModelComparePanel'
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
import { FileText, Settings, RotateCcw, LayoutDashboard, Activity, Brain, Sliders, GitCompare, Puzzle, Copy, FileCode, BarChart3, ArrowDownToLine, Search, FolderOpen, GitBranch, Zap, Users, LineChart, Shield } from 'lucide-react'

const tabs = [
  { id: 'files', label: 'Docs', icon: FileText },
  { id: 'dashboard', label: 'Dash', icon: LayoutDashboard },
  { id: 'catalog', label: 'Models', icon: Brain },
  { id: 'compare', label: 'Compare', icon: GitCompare },
  { id: 'templates', label: 'Prompts', icon: Copy },
  { id: 'diff', label: 'Diff', icon: FileCode },
  { id: 'profiling', label: 'Profile', icon: Activity },
  { id: 'analytics', label: 'Stats', icon: BarChart3 },
  { id: 'replay', label: 'Replay', icon: RotateCcw },
  { id: 'plugins', label: 'Plugins', icon: Puzzle },
  { id: 'export', label: 'Export', icon: ArrowDownToLine },
  { id: 'search', label: 'Search', icon: Search },
  { id: 'workspace', label: 'Spaces', icon: FolderOpen },
  { id: 'workflows', label: 'Flows', icon: GitBranch },
  { id: 'canvas', label: 'Canvas', icon: GitBranch },
  { id: 'collab', label: 'Collab', icon: Users },
  { id: 'benchmark', label: 'Bench', icon: Zap },
  { id: 'benchchart', label: 'Charts', icon: LineChart },
  { id: 'sandbox', label: 'Sandbox', icon: Shield },
  { id: 'config', label: 'Config', icon: Sliders },
  { id: 'settings', label: 'Settings', icon: Settings },
]

export function RightPanel() {
  const { rightPanelTab, setRightPanelTab } = useUIStore()
  const [selectedFile, setSelectedFile] = useState<string | null>(null)

  function handleFileSelect(path: string) {
    setSelectedFile(path)
  }

  return (
    <aside className="w-80 h-full flex flex-col bg-surface border-l border-border" aria-label="Right panel">
      {/* Tab bar */}
      <div className="flex border-b border-border" role="tablist" aria-label="Panel tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const active = rightPanelTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => {
                setRightPanelTab(tab.id)
                if (tab.id === 'files') setSelectedFile(null)
              }}
              role="tab"
              aria-selected={active}
              aria-controls={`panel-${tab.id}`}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[11px] font-medium transition-colors relative ${
                active
                  ? 'text-accent border-b-2 border-accent'
                  : 'text-text-muted hover:text-text-sec'
              }`}
            >
              <Icon size={13} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {rightPanelTab === 'files' && !selectedFile && (
          <FileExplorer onFileSelect={handleFileSelect} selectedFile={selectedFile} />
        )}
        {rightPanelTab === 'files' && selectedFile && (
          <FileViewer filePath={selectedFile} onClose={() => setSelectedFile(null)} />
        )}
        {rightPanelTab === 'dashboard' && (
          <WorkspaceDashboard />
        )}
        {rightPanelTab === 'catalog' && (
          <ModelCatalogPanel />
        )}
        {rightPanelTab === 'compare' && (
          <ModelComparePanel />
        )}
        {rightPanelTab === 'profiling' && (
          <ProfilingPanel />
        )}
        {rightPanelTab === 'replay' && (
          <SessionReplayPanel />
        )}
        {rightPanelTab === 'plugins' && (
          <PluginMarketplacePanel />
        )}
        {rightPanelTab === 'templates' && (
          <TemplatePanel />
        )}
        {rightPanelTab === 'diff' && (
          <DiffViewerPanel />
        )}
        {rightPanelTab === 'analytics' && (
          <AnalyticsDashboard />
        )}
        {rightPanelTab === 'export' && (
          <ExportImportPanel />
        )}
        {rightPanelTab === 'search' && (
          <AdvancedSearchPanel />
        )}
        {rightPanelTab === 'workspace' && (
          <WorkspaceManagerPanel />
        )}
        {rightPanelTab === 'workflows' && (
          <WorkflowBuilderPanel />
        )}
        {rightPanelTab === 'canvas' && (
          <WorkflowCanvas />
        )}
        {rightPanelTab === 'collab' && (
          <CollabPanel />
        )}
        {rightPanelTab === 'benchmark' && (
          <BenchmarkPanel />
        )}
        {rightPanelTab === 'benchchart' && (
          <BenchmarkChartPanel />
        )}
        {rightPanelTab === 'sandbox' && (
          <PluginSandboxPanel />
        )}
        {rightPanelTab === 'config' && (
          <AgentConfigPanel />
        )}
        {rightPanelTab === 'settings' && (
          <SettingsDialog onClose={() => setRightPanelTab('files')} />
        )}
      </div>
    </aside>
  )
}
