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
  Shield,
  AlertTriangle,
  AlertOctagon,
} from 'lucide-react'
import { MarkdownRenderer } from '../chat/MarkdownRenderer'
import type { ToolCall } from '../../stores/chatStore'

interface Props {
  tool: ToolCall
  onApprove?: (id: string, approved: boolean) => void
}

// Risk classification based on tool name (matches OpenHands pattern)
const TOOL_RISK: Record<string, 'low' | 'medium' | 'high'> = {
  read_file: 'low',
  list_files: 'low',
  search_files: 'low',
  get_file: 'low',
  write_file: 'medium',
  edit_file: 'medium',
  create_file: 'medium',
  run_terminal_command: 'high',
  delete_file: 'high',
  bash: 'high',
  shell: 'high',
}

function getToolRisk(name: string): 'low' | 'medium' | 'high' {
  const lower = name.toLowerCase()
  for (const [key, risk] of Object.entries(TOOL_RISK)) {
    if (lower.includes(key)) return risk
  }
  if (lower.includes('read') || lower.includes('get') || lower.includes('list') || lower.includes('search')) return 'low'
  if (lower.includes('write') || lower.includes('edit') || lower.includes('create') || lower.includes('update')) return 'medium'
  return 'high'
}

const RISK_CONFIG = {
  low: { icon: Shield, label: 'LOW', color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30' },
  medium: { icon: AlertTriangle, label: 'MED', color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30' },
  high: { icon: AlertOctagon, label: 'HIGH', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30' },
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
    label: 'Done',
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
    label: 'Awaiting',
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    animate: false,
  },
}

export function ToolCallCard({ tool, onApprove }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const [duration, setDuration] = useState<number | null>(null)
  const [startTime] = useState(Date.now())
  const config = STATUS_CONFIG[tool.status]
  const Icon = config.icon
  const risk = getToolRisk(tool.name)
  const riskConfig = RISK_CONFIG[risk]
  const RiskIcon = riskConfig.icon

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

  // Compact chip mode during streaming
  if (tool.status === 'running' && !expanded) {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/30 text-xs animate-slide-up">
        <Loader2 size={10} className="text-accent animate-spin" />
        <span className="text-text font-medium">{tool.name}</span>
        <span className="text-text-muted font-mono text-[10px]">
          {formatDuration(duration || 0)}
        </span>
      </div>
    )
  }

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} overflow-hidden animate-slide-up`}>
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

          {/* Risk badge */}
          <span className={`inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full ${riskConfig.bg} ${riskConfig.color} ${riskConfig.border} border font-medium`}>
            <RiskIcon size={9} />
            {riskConfig.label}
          </span>

          {/* Duration */}
          {duration !== null && (
            <span className="text-[10px] text-text-muted font-mono">
              {formatDuration(duration)}
            </span>
          )}

          <span className={`text-xs ${config.color}`}>{config.label}</span>
        </button>

        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="p-1 text-text-muted hover:text-text rounded transition-colors opacity-0 group-hover:opacity-100"
            title="Copy args"
          >
            {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
          </button>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border/50 px-3 py-2 space-y-2 animate-fade-in">
          {/* Arguments */}
          {Object.keys(tool.args).length > 0 && (
            <div>
              <div className="text-xs text-text-muted mb-1 font-medium">Arguments</div>
              <pre className="text-xs bg-bg/50 rounded p-2 overflow-x-auto text-text-sec border border-border/30">
                {JSON.stringify(tool.args, null, 2)}
              </pre>
            </div>
          )}

          {/* Result */}
          {tool.result && (
            <div>
              <div className="text-xs text-text-muted mb-1 font-medium">Result</div>
              <div className="text-xs bg-bg/50 rounded p-2 max-h-40 overflow-y-auto border border-border/30">
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
