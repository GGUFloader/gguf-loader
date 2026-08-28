import { useState } from 'react'
import { AlertTriangle, Shield, CheckCircle2, XCircle, ShieldCheck, ShieldAlert, Ban } from 'lucide-react'
import type { ToolApprovalRequest } from '../../stores/chatStore'

interface Props {
  request: ToolApprovalRequest
  onApprove: (id: string, approved: boolean) => void
  onApproveAll?: () => void
  onSkipAll?: () => void
  totalPending?: number
}

const TOOL_RISK: Record<string, { risk: 'low' | 'medium' | 'high'; description: string }> = {
  read_file: { risk: 'low', description: 'Reads a file from the workspace' },
  list_files: { risk: 'low', description: 'Lists directory contents' },
  search_files: { risk: 'low', description: 'Searches file contents' },
  get_file: { risk: 'low', description: 'Gets file content' },
  write_file: { risk: 'medium', description: 'Creates or overwrites a file' },
  edit_file: { risk: 'medium', description: 'Modifies an existing file' },
  create_file: { risk: 'medium', description: 'Creates a new file' },
  run_terminal_command: { risk: 'high', description: 'Executes a shell command' },
  bash: { risk: 'high', description: 'Runs a shell command' },
  shell: { risk: 'high', description: 'Runs a shell command' },
  delete_file: { risk: 'high', description: 'Permanently deletes a file' },
}

const RISK_COLORS = {
  low: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30', icon: Shield },
  medium: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30', icon: ShieldAlert },
  high: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30', icon: ShieldCheck },
}

export function ToolApprovalDialog({ request, onApprove, onApproveAll, onSkipAll, totalPending = 1 }: Props) {
  const [dontAskAgain, setDontAskAgain] = useState(false)
  const toolInfo = TOOL_RISK[request.tool] || { risk: 'medium' as const, description: 'Unknown tool — proceed with caution' }
  const colors = RISK_COLORS[toolInfo.risk]
  const RiskIcon = colors.icon

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 animate-fade-in">
      <div className="bg-elevated border border-border rounded-xl shadow-2xl max-w-md w-full mx-4 overflow-hidden animate-scale-in">
        {/* Header */}
        <div className={`flex items-center gap-3 px-5 py-4 ${colors.bg} border-b ${colors.border}`}>
          {toolInfo.risk === 'high' ? (
            <AlertTriangle size={20} className={colors.text} />
          ) : (
            <RiskIcon size={20} className={colors.text} />
          )}
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-text">Tool Approval Required</h3>
            <p className="text-xs text-text-muted">{toolInfo.description}</p>
          </div>
          {totalPending > 1 && (
            <span className="text-xs bg-bg/50 px-2 py-0.5 rounded-full text-text-muted">
              {totalPending} pending
            </span>
          )}
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-3">
          {/* Tool name + risk badge */}
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-text font-mono">{request.tool}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${colors.bg} ${colors.text} ${colors.border} border font-medium`}>
              {toolInfo.risk} risk
            </span>
          </div>

          {/* Arguments preview */}
          <div>
            <div className="text-xs text-text-muted mb-1">Arguments</div>
            <pre className="text-xs bg-bg rounded-lg p-3 overflow-x-auto text-text-sec max-h-48 overflow-y-auto border border-border font-mono">
              {JSON.stringify(request.args, null, 2)}
            </pre>
          </div>

          {/* Don't ask again checkbox */}
          <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer select-none">
            <input
              type="checkbox"
              checked={dontAskAgain}
              onChange={(e) => setDontAskAgain(e.target.checked)}
              className="rounded border-border accent-accent"
            />
            Don't ask again for this session
          </label>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-border bg-bg/30">
          {/* Left side: batch actions */}
          <div className="flex items-center gap-2">
            {totalPending > 1 && onApproveAll && (
              <button
                onClick={onApproveAll}
                className="flex items-center gap-1 px-3 py-1.5 bg-green-500/10 text-green-400 rounded-lg text-xs font-medium hover:bg-green-500/20 transition-colors"
              >
                <CheckCircle2 size={12} />
                Approve All ({totalPending})
              </button>
            )}
            {totalPending > 1 && onSkipAll && (
              <button
                onClick={onSkipAll}
                className="flex items-center gap-1 px-3 py-1.5 bg-bg text-text-muted rounded-lg text-xs font-medium hover:bg-elevated transition-colors"
              >
                <Ban size={12} />
                Skip All
              </button>
            )}
          </div>

          {/* Right side: single approve/deny */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => onApprove(request.id, false)}
              className="flex items-center gap-1.5 px-4 py-2 bg-red-500/10 text-red-400 rounded-lg text-sm font-medium hover:bg-red-500/20 transition-colors"
            >
              <XCircle size={14} />
              Deny
            </button>
            <button
              onClick={() => onApprove(request.id, true)}
              className="flex items-center gap-1.5 px-4 py-2 bg-green-500/20 text-green-400 rounded-lg text-sm font-medium hover:bg-green-500/30 transition-colors"
            >
              <CheckCircle2 size={14} />
              Approve
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
