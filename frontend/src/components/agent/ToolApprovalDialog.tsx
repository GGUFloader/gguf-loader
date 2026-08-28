import { AlertTriangle, Shield, CheckCircle2, XCircle } from 'lucide-react'
import type { ToolApprovalRequest } from '../../stores/chatStore'

interface Props {
  request: ToolApprovalRequest
  onApprove: (id: string, approved: boolean) => void
}

const TOOL_RISK: Record<string, { risk: 'low' | 'medium' | 'high'; description: string }> = {
  read_file: { risk: 'low', description: 'Reads a file from the workspace' },
  list_files: { risk: 'low', description: 'Lists directory contents' },
  search_files: { risk: 'low', description: 'Searches file contents' },
  write_file: { risk: 'medium', description: 'Creates or overwrites a file' },
  edit_file: { risk: 'medium', description: 'Modifies an existing file' },
  run_terminal_command: { risk: 'high', description: 'Executes a shell command' },
  delete_file: { risk: 'high', description: 'Permanently deletes a file' },
}

const RISK_COLORS = {
  low: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30' },
  medium: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  high: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
}

export function ToolApprovalDialog({ request, onApprove }: Props) {
  const toolInfo = TOOL_RISK[request.tool] || { risk: 'medium' as const, description: 'Unknown tool' }
  const colors = RISK_COLORS[toolInfo.risk]

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-elevated border border-border rounded-xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className={`flex items-center gap-3 px-5 py-4 ${colors.bg} border-b ${colors.border}`}>
          {toolInfo.risk === 'high' ? (
            <AlertTriangle size={20} className={colors.text} />
          ) : (
            <Shield size={20} className={colors.text} />
          )}
          <div>
            <h3 className="text-sm font-semibold text-text">Tool Approval Required</h3>
            <p className="text-xs text-text-muted">{toolInfo.description}</p>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-3">
          {/* Tool name + risk badge */}
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-text">{request.tool}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${colors.bg} ${colors.text} ${colors.border} border`}>
              {toolInfo.risk} risk
            </span>
          </div>

          {/* Arguments preview */}
          <div>
            <div className="text-xs text-text-muted mb-1">Arguments</div>
            <pre className="text-xs bg-bg rounded-lg p-3 overflow-x-auto text-text-sec max-h-48 overflow-y-auto border border-border">
              {JSON.stringify(request.args, null, 2)}
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border bg-bg/30">
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
  )
}
