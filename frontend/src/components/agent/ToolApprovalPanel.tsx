import { Shield, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import type { ToolApprovalRequest } from '../../stores/chatStore'

interface Props {
  onApprove: (id: string, approved: boolean) => void
}

export function ToolApprovalPanel({ onApprove }: Props) {
  const { pendingApprovals } = useChatStore()

  if (pendingApprovals.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-4">
        <Shield size={32} className="text-text-muted mb-3" />
        <p className="text-sm text-text-muted">No pending approvals</p>
        <p className="text-xs text-text-muted mt-1">
          Tool calls requiring approval will appear here
        </p>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-2">
      <div className="flex items-center gap-2 px-2 py-1">
        <AlertTriangle size={14} className="text-yellow-400" />
        <span className="text-xs font-medium text-text">
          {pendingApprovals.length} pending
        </span>
      </div>

      {pendingApprovals.map((req) => (
        <ApprovalCard key={req.id} request={req} onApprove={onApprove} />
      ))}
    </div>
  )
}

function ApprovalCard({
  request,
  onApprove,
}: {
  request: ToolApprovalRequest
  onApprove: (id: string, approved: boolean) => void
}) {
  return (
    <div className="bg-elevated border border-yellow-500/30 rounded-lg overflow-hidden">
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 mb-1">
          <AlertTriangle size={12} className="text-yellow-400" />
          <span className="text-sm font-medium text-text">{request.tool}</span>
        </div>

        <pre className="text-xs bg-bg/50 rounded p-2 overflow-x-auto text-text-sec max-h-24 overflow-y-auto">
          {JSON.stringify(request.args, null, 2)}
        </pre>
      </div>

      <div className="flex items-center gap-1 px-3 py-2 border-t border-border/50">
        <button
          onClick={() => onApprove(request.id, true)}
          className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-green-500/15 text-green-400 rounded text-xs font-medium hover:bg-green-500/25 transition-colors"
        >
          <CheckCircle2 size={12} />
          Allow
        </button>
        <button
          onClick={() => onApprove(request.id, false)}
          className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-red-500/15 text-red-400 rounded text-xs font-medium hover:bg-red-500/25 transition-colors"
        >
          <XCircle size={12} />
          Deny
        </button>
      </div>
    </div>
  )
}
