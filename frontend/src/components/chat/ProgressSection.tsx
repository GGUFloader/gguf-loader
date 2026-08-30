import { useState } from 'react'
import { ChevronDown, ChevronRight, CheckCircle2, Loader2 } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'

export function ProgressSection() {
  const [expanded, setExpanded] = useState(true)
  const { progressSteps, isStreaming } = useChatStore()

  // Filter to announce and message steps (the main progress items)
  const mainSteps = progressSteps.filter(s => s.type === 'announce' || s.type === 'message')
  const hasSteps = mainSteps.length > 0 || isStreaming

  if (!hasSteps) return null

  return (
    <div className="border-b border-border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-elevated/30 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={14} className="text-text-muted" />
        ) : (
          <ChevronRight size={14} className="text-text-muted" />
        )}
        <span className="text-sm font-medium text-text">Progress</span>
        {mainSteps.length > 0 && (
          <span className="text-[10px] text-text-muted ml-auto">{mainSteps.length} steps</span>
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-1.5">
          {mainSteps.map((step) => (
            <div key={step.id} className="flex items-start gap-2">
              <CheckCircle2 size={14} className="text-green-400 mt-0.5 flex-shrink-0" />
              <span className="text-xs text-text-sec leading-relaxed">{step.content}</span>
            </div>
          ))}
          {isStreaming && (
            <div className="flex items-start gap-2">
              <Loader2 size={14} className="text-accent animate-spin mt-0.5 flex-shrink-0" />
              <span className="text-xs text-accent">Working...</span>
            </div>
          )}
          {mainSteps.length === 0 && !isStreaming && (
            <p className="text-xs text-text-muted">Steps will show as the task unfolds.</p>
          )}
        </div>
      )}
    </div>
  )
}
