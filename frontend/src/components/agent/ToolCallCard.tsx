import { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Copy,
  Check,
} from 'lucide-react'
import { MarkdownRenderer } from '../chat/MarkdownRenderer'
import type { ToolCall } from '../../stores/chatStore'

interface Props {
  tool: ToolCall
  onApprove?: (id: string, approved: boolean) => void
}

const STATUS_CONFIG = {
  running: {
    icon: Loader2,
    label: 'Running',
    color: 'text-accent',
    bg: 'bg-accent/10',
    border: 'border-accent/30',
    animate: true,
  },
  completed: {
    icon: CheckCircle2,
    label: 'Completed',
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    animate: false,
  },
  failed: {
    icon: XCircle,
    label: 'Failed',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    animate: false,
  },
  pending_approval: {
    icon: Clock,
    label: 'Awaiting Approval',
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    animate: false,
  },
}

export function ToolCallCard({ tool, onApprove }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const config = STATUS_CONFIG[tool.status]
  const Icon = config.icon

  function handleCopy() {
    const text = JSON.stringify(tool.args, null, 2)
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 flex-1 text-left"
        >
          {expanded ? (
            <ChevronDown size={14} className="text-text-muted" />
          ) : (
            <ChevronRight size={14} className="text-text-muted" />
          )}
          <Icon
            size={14}
            className={`${config.color} ${config.animate ? 'animate-spin' : ''}`}
          />
          <span className="text-sm font-medium text-text">{tool.name}</span>
          <span className={`text-xs ${config.color}`}>{config.label}</span>
        </button>

        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="p-1 text-text-muted hover:text-text rounded transition-colors"
            title="Copy args"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
          </button>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border/50 px-3 py-2 space-y-2">
          {/* Arguments */}
          {Object.keys(tool.args).length > 0 && (
            <div>
              <div className="text-xs text-text-muted mb-1">Arguments</div>
              <pre className="text-xs bg-bg/50 rounded p-2 overflow-x-auto text-text-sec">
                {JSON.stringify(tool.args, null, 2)}
              </pre>
            </div>
          )}

          {/* Result */}
          {tool.result && (
            <div>
              <div className="text-xs text-text-muted mb-1">Result</div>
              <div className="text-xs bg-bg/50 rounded p-2 max-h-40 overflow-y-auto">
                <MarkdownRenderer content={tool.result} />
              </div>
            </div>
          )}

          {/* Approval buttons */}
          {tool.status === 'pending_approval' && onApprove && tool.approvalId && (
            <div className="flex items-center gap-2 pt-1">
              <button
                onClick={() => onApprove(tool.approvalId!, true)}
                className="flex items-center gap-1 px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-xs font-medium hover:bg-green-500/30 transition-colors"
              >
                <CheckCircle2 size={12} />
                Approve
              </button>
              <button
                onClick={() => onApprove(tool.approvalId!, false)}
                className="flex items-center gap-1 px-3 py-1.5 bg-red-500/20 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/30 transition-colors"
              >
                <XCircle size={12} />
                Deny
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
