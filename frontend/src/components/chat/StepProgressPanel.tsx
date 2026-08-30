import { useState, useRef, useEffect } from 'react'
import { ChevronDown, ChevronRight, CheckCircle2, Loader2, Eye } from 'lucide-react'
import { MarkdownRenderer } from './MarkdownRenderer'

export interface ProgressStep {
  id: string
  type: 'announce' | 'tool_call' | 'tool_result' | 'message' | 'error' | 'thinking'
  content: string
  timestamp: number
  toolName?: string
  toolArgs?: Record<string, any>
  toolResult?: string
  success?: boolean
  /** Sub-steps completed under this announce */
  completedSteps?: number
  /** Whether this step is currently in progress */
  active?: boolean
}

interface Props {
  steps: ProgressStep[]
  isStreaming: boolean
  currentAnnouncement?: string
}

function StepCard({ step, index, allSteps }: { step: ProgressStep; index: number; allSteps: ProgressStep[] }) {
  const [expanded, setExpanded] = useState(false)


  // Count consecutive tool results after this announce step
  let subStepCount = 0
  if (step.type === 'announce') {
    for (let i = index + 1; i < allSteps.length; i++) {
      const next = allSteps[i]
      if (next.type === 'announce' || next.type === 'message') break
      if (next.type === 'tool_call' || next.type === 'tool_result' || next.type === 'thinking') {
        subStepCount++
      }
    }
  }

  // Announce steps — the big "Found the issues. Let me fix them all..." style
  if (step.type === 'announce') {
    return (
      <div className="animate-slide-up">
        {/* Main announcement text */}
        <div className="text-sm text-text leading-relaxed pl-8 pr-4">
          <MarkdownRenderer content={step.content} />
        </div>

        {/* Collapsible sub-steps */}
        {subStepCount > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-2 ml-8 mt-1.5 px-2 py-1 rounded-md hover:bg-elevated transition-colors group"
          >
            {expanded ? (
              <ChevronDown size={12} className="text-text-muted" />
            ) : (
              <ChevronRight size={12} className="text-text-muted" />
            )}
            <span className="text-xs text-text-muted group-hover:text-text-sec transition-colors">
              Worked · {subStepCount} step{subStepCount !== 1 ? 's' : ''}
            </span>
          </button>
        )}

        {/* Expanded sub-steps list */}
        {expanded && subStepCount > 0 && (
          <div className="ml-8 mt-1 space-y-0.5 border-l border-border/50 pl-3">
            {allSteps.slice(index + 1, index + 1 + subStepCount).map((sub) => (
              <SubStepRow key={sub.id} step={sub} />
            ))}
          </div>
        )}
      </div>
    )
  }

  // Message type — assistant prose (same as announce but different styling context)
  if (step.type === 'message') {
    return (
      <div className="animate-slide-up pl-8 pr-4">
        <div className="text-sm text-text leading-relaxed">
          <MarkdownRenderer content={step.content} />
        </div>
      </div>
    )
  }

  // Thinking blocks — shown inline but collapsible
  if (step.type === 'thinking') {
    return (
      <div className="animate-slide-up">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 ml-8 px-2 py-1 rounded-md hover:bg-elevated transition-colors group"
        >
          {expanded ? (
            <ChevronDown size={12} className="text-purple-400" />
          ) : (
            <ChevronRight size={12} className="text-purple-400" />
          )}
          <Eye size={12} className="text-purple-400" />
          <span className="text-xs text-purple-400/80 group-hover:text-purple-400 transition-colors">
            Reasoning
          </span>
        </button>
        {expanded && (
          <div className="ml-8 mt-1 pl-3 border-l border-purple-500/20">
            <div className="text-xs text-text-sec whitespace-pre-wrap font-mono leading-relaxed max-h-60 overflow-y-auto bg-purple-500/5 rounded p-2">
              {step.content}
            </div>
          </div>
        )}
      </div>
    )
  }

  // Error
  if (step.type === 'error') {
    return (
      <div className="animate-slide-up ml-8 pr-4">
        <div className="text-sm text-red-400 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">
          {step.content}
        </div>
      </div>
    )
  }

  // Tool call / result — shown as part of sub-step list, not standalone
  return null
}

function SubStepRow({ step }: { step: ProgressStep }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetail = step.toolResult || (step.toolArgs && Object.keys(step.toolArgs).length > 0)

  return (
    <div className="py-0.5">
      <div className="flex items-center gap-2 text-xs">
        {step.type === 'tool_call' && (
          <>
            {step.active ? (
              <Loader2 size={10} className="text-accent animate-spin flex-shrink-0" />
            ) : (
              <CheckCircle2 size={10} className="text-green-400 flex-shrink-0" />
            )}
            <span className="text-text-sec">
              {getToolDescription(step)}
            </span>
          </>
        )}
        {step.type === 'tool_result' && (
          <>
            {step.success !== false ? (
              <CheckCircle2 size={10} className="text-green-400 flex-shrink-0" />
            ) : (
              <CheckCircle2 size={10} className="text-red-400 flex-shrink-0" />
            )}
            <span className="text-text-muted">
              {step.content.slice(0, 80)}{step.content.length > 80 ? '...' : ''}
            </span>
          </>
        )}
      </div>

      {/* Expandable detail */}
      {hasDetail && expanded && (
        <div className="ml-5 mt-1 space-y-1">
          {step.toolArgs && Object.keys(step.toolArgs).length > 0 && (
            <div className="text-[10px] text-text-muted bg-bg/50 rounded p-1.5 font-mono overflow-x-auto">
              {JSON.stringify(step.toolArgs, null, 2).slice(0, 300)}
              {JSON.stringify(step.toolArgs, null, 2).length > 300 && '...'}
            </div>
          )}
          {step.toolResult && (
            <div className="text-[10px] text-text-sec bg-bg/50 rounded p-1.5 max-h-20 overflow-y-auto">
              {step.toolResult.slice(0, 200)}{step.toolResult.length > 200 ? '...' : ''}
            </div>
          )}
        </div>
      )}

      {hasDetail && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="ml-5 text-[10px] text-text-muted hover:text-text-sec transition-colors"
        >
          {expanded ? 'less' : 'more'}
        </button>
      )}
    </div>
  )
}

/** Human-readable description for tool calls */
function getToolDescription(step: ProgressStep): string {
  const name = step.toolName || 'tool'
  const args = step.toolArgs || {}

  // Map common tools to human descriptions
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
      return `Running \`${(args.command || '').slice(0, 40)}\``
    case 'code_search':
      return `Searching for "${(args.pattern || '').slice(0, 30)}"`
    case 'glob':
      return `Finding files matching ${(args.pattern || '')}`
    case 'web_search':
      return `Searching web for "${(args.query || '').slice(0, 30)}"`
    case 'suggest_prompts':
      return `Suggesting follow-ups`
    case 'ask_questions':
      return `Asking user a question`
    case 'write_todos':
      return `Updating task list`
    default:
      return `Running ${name}`
  }
}

export function StepProgressPanel({ steps, isStreaming, currentAnnouncement }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll on new steps
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 150
      if (isNearBottom || isStreaming) {
        el.scrollTop = el.scrollHeight
      }
    }
  }, [steps.length, currentAnnouncement])

  if (steps.length === 0 && !currentAnnouncement) return null

  return (
    <div ref={scrollRef} className="space-y-2">
      {/* Rendered steps */}
      {steps.map((step, i) => (
        <StepCard
          key={step.id}
          step={step}
          index={i}
          allSteps={steps}
        />
      ))}

      {/* Live announcement (streaming, not yet committed) */}
      {currentAnnouncement && isStreaming && (
        <div className="animate-slide-up flex items-center gap-2 pl-8 pr-4">
          <div className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse flex-shrink-0" />
          <div className="text-sm text-text/80 leading-relaxed">
            <MarkdownRenderer content={currentAnnouncement} />
          </div>
        </div>
      )}

      {/* Active tool indicator */}
      {isStreaming && !currentAnnouncement && steps.length > 0 && (
        <div className="flex items-center gap-2 pl-8 py-1">
          <Loader2 size={12} className="text-accent animate-spin" />
          <span className="text-xs text-text-muted">Working...</span>
        </div>
      )}
    </div>
  )
}
