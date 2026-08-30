import { useState, useEffect } from 'react'
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
    animate: true,
  },
  completed: {
    icon: CheckCircle2,
    label: 'Done',
    color: 'text-green-400',
    animate: false,
  },
  failed: {
    icon: XCircle,
    label: 'Failed',
    color: 'text-red-400',
    animate: false,
  },
  pending_approval: {
    icon: Clock,
    label: 'Awaiting approval',
    color: 'text-yellow-400',
    animate: false,
  },
}

/** Human-readable description for tool calls */
function getToolDescription(tool: ToolCall): string {
  const name = tool.name
  const args = tool.args || {}

  switch (name.toLowerCase()) {
    case 'read_files':
    case 'read_file':
      return `Reading ${(args.paths || [args.path] || []).map((p: string) => p.split('/').pop()).join(', ')}`
    case 'write_file':
      return `Writing ${(args.path || '').split('/').pop() || 'file'}`
    case 'str_replace':
      return `Editing ${(args.path || '').split('/').pop() || 'file'}`
    case 'list_directory':
      return `Listing ${(args.path || '').split('/').pop() || 'directory'}`
    case 'run_terminal_command':
      return `Running command`
    case 'code_search':
      return `Searching for "${(args.pattern || '').slice(0, 30)}"`
    case 'glob':
      return `Finding files`
    case 'web_search':
      return `Searching web`
    default:
      return `Using ${name}`
  }
}

export function ToolCallCard({ tool, onApprove }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const [duration, setDuration] = useState<number | null>(null)
  const [startTime] = useState(Date.now())
  const config = STATUS_CONFIG[tool.status]
  const Icon = config.icon

  // Track duration while running
  useEffect(() => {
    if (tool.status !== 'running') {
      if (duration === null) setDuration(Date.now() - startTime)
      return
    }
    const interval = setInterval(() => {
      setDuration(Date.now() - startTime)
    }, 100)
    return () => clearInterval(interval)
  }, [tool.status, startTime, duration])

  function handleCopy() {
    const text = JSON.stringify(tool.args, null, 2)
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const description = getToolDescription(tool)
  const hasDetails = Object.keys(tool.args).length > 0 || tool.result

  return (
    <div className="ml-0 animate-slide-up">
      {/* Collapsed header — always visible */}
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        className={`w-full flex items-center gap-2 px-3 py-2 rounded-xl border transition-colors ${
          tool.status === 'running'
            ? 'bg-accent/5 border-accent/20'
            : tool.status === 'completed'
              ? 'bg-elevated/50 border-border/50 hover:bg-elevated'
              : tool.status === 'failed'
                ? 'bg-red-500/5 border-red-500/20'
                : 'bg-yellow-500/5 border-yellow-500/20'
        } ${hasDetails ? 'cursor-pointer' : ''}`}
      >
        {/* Expand/collapse chevron */}
        {hasDetails ? (
          expanded ? (
            <ChevronDown size={14} className="text-text-muted flex-shrink-0" />
          ) : (
            <ChevronRight size={14} className="text-text-muted flex-shrink-0" />
          )
        ) : (
          <div className="w-3.5" />
        )}

        {/* Status icon */}
        <Icon
          size={14}
          className={`${config.color} flex-shrink-0 ${config.animate ? 'animate-spin' : ''}`}
        />

        {/* Description */}
        <span className="text-sm text-text-sec flex-1 text-left">{description}</span>

        {/* Duration */}
        {duration !== null && (
          <span className="text-[10px] text-text-muted font-mono flex-shrink-0">
            {formatDuration(duration)}
          </span>
        )}

        {/* Status label */}
        <span className={`text-[11px] flex-shrink-0 ${config.color}`}>{config.label}</span>

        {/* Copy button */}
        {hasDetails && (
          <button
            onClick={(e) => { e.stopPropagation(); handleCopy() }}
            className="p-1 text-text-muted hover:text-text rounded transition-colors opacity-0 group-hover:opacity-100"
            title="Copy args"
          >
            {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
          </button>
        )}
      </button>

      {/* Expanded content — command/args in code block */}
      {expanded && (
        <div className="mt-1 ml-8 space-y-2 animate-fade-in">
          {/* Arguments as code block */}
          {Object.keys(tool.args).length > 0 && (
            <div>
              <div className="text-[10px] text-text-muted mb-1 font-medium uppercase tracking-wider">Request</div>
              <pre className="text-xs bg-bg/80 rounded-lg p-3 overflow-x-auto text-text-sec border border-border/50 font-mono leading-relaxed">
                {JSON.stringify(tool.args, null, 2)}
              </pre>
            </div>
          )}

          {/* Result */}
          {tool.result && (
            <div>
              <div className="text-[10px] text-text-muted mb-1 font-medium uppercase tracking-wider">Result</div>
              <div className="text-xs bg-bg/80 rounded-lg p-3 max-h-40 overflow-y-auto border border-border/50">
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
