import { useState } from 'react'
import { useUIStore } from '../../stores/uiStore'
import { useChatStore } from '../../stores/chatStore'
import { ToolApprovalPanel } from '../agent/ToolApprovalPanel'
import { FileExplorer } from '../workbench/FileExplorer'
import { FileViewer } from '../workbench/FileViewer'
import { Terminal } from '../workbench/Terminal'
import { GitPanel } from '../workbench/GitPanel'
import { SettingsDialog } from '../settings/SettingsDialog'
import { FileCode, Terminal as TerminalIcon, GitBranch, Settings, Shield, Server, Wrench, GitBranch as WorkflowIcon, Puzzle } from 'lucide-react'
import { MCPPanel } from '../agent/MCPPanel'
import { ToolBrowserPanel } from '../agent/ToolBrowserPanel'
import { WorkflowPanel } from '../agent/WorkflowPanel'
import { PluginPanel } from '../agent/PluginPanel'

const tabs = [
  { id: 'files', label: 'Files', icon: FileCode },
  { id: 'terminal', label: 'Terminal', icon: TerminalIcon },
  { id: 'git', label: 'Git', icon: GitBranch },
  { id: 'approvals', label: 'Approvals', icon: Shield },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'mcp', label: 'MCP', icon: Server },
  { id: 'workflows', label: 'Flow', icon: WorkflowIcon },
  { id: 'plugins', label: 'Plugins', icon: Puzzle },
  { id: 'settings', label: 'Settings', icon: Settings },
]

export function RightPanel() {
  const { rightPanelTab, setRightPanelTab } = useUIStore()
  const { pendingApprovals } = useChatStore()
  const [selectedFile, setSelectedFile] = useState<string | null>(null)

  function handleApprove(id: string, approved: boolean) {
    fetch('/api/agent/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ call_id: id, approved }),
    })
  }

  function handleFileSelect(path: string) {
    setSelectedFile(path)
  }

  return (
    <div className="w-80 h-full flex flex-col bg-surface border-l border-border">
      {/* Tab bar */}
      <div className="flex border-b border-border">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const active = rightPanelTab === tab.id
          const hasBadge = tab.id === 'approvals' && pendingApprovals.length > 0
          return (
            <button
              key={tab.id}
              onClick={() => {
                setRightPanelTab(tab.id)
                if (tab.id !== 'files') setSelectedFile(null)
              }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors relative ${
                active
                  ? 'text-accent border-b-2 border-accent'
                  : 'text-text-muted hover:text-text-sec'
              }`}
            >
              <Icon size={14} />
              {tab.label}
              {hasBadge && (
                <span className="absolute top-1 right-1 w-4 h-4 bg-yellow-500 text-black text-[10px] font-bold rounded-full flex items-center justify-center">
                  {pendingApprovals.length}
                </span>
              )}
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
        {rightPanelTab === 'terminal' && <Terminal />}
        {rightPanelTab === 'git' && <GitPanel />}
        {rightPanelTab === 'approvals' && (
          <ToolApprovalPanel onApprove={handleApprove} />
        )}
        {rightPanelTab === 'tools' && <ToolBrowserPanel />}
        {rightPanelTab === 'mcp' && <MCPPanel />}
        {rightPanelTab === 'workflows' && <WorkflowPanel />}
        {rightPanelTab === 'plugins' && <PluginPanel />}
        {rightPanelTab === 'settings' && (
          <SettingsDialog onClose={() => setRightPanelTab('files')} />
        )}
      </div>
    </div>
  )
}
