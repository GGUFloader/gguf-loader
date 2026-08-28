import { useState } from 'react'
import { ChevronDown, Brain } from 'lucide-react'

interface Props {
  content: string
  isStreaming?: boolean
}

export function ReasoningBlock({ content, isStreaming }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (!content) return null

  return (
    <div className="my-2 border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-elevated/50 hover:bg-elevated transition-colors text-sm"
      >
        <Brain size={14} className="text-accent" />
        <span className="text-text-sec font-medium">Thinking</span>
        {isStreaming && (
          <span className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse" />
        )}
        <ChevronDown
          size={14}
          className={`ml-auto text-text-muted transition-transform ${
            expanded ? 'rotate-180' : ''
          }`}
        />
      </button>

      {expanded && (
        <div className="px-3 py-2 bg-elevated/30 border-t border-border">
          <div className="text-sm text-text-sec whitespace-pre-wrap font-mono leading-relaxed">
            {content}
          </div>
        </div>
      )}

      {!expanded && (
        <div className="px-3 py-1.5 text-xs text-text-muted truncate">
          {content.substring(0, 100)}...
        </div>
      )}
    </div>
  )
}
