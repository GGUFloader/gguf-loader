import { useState } from 'react'
import { ChevronDown, Brain, Loader2 } from 'lucide-react'

interface Props {
  content: string
  isStreaming?: boolean
}

export function ReasoningBlock({ content, isStreaming }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (!content) return null

  // Clean up raw status lines from the agent engine
  const cleanContent = content
    .split('\n')
    .filter(line => !line.match(/^(Goal:|Plan \(|Step \d|Verif|All plan|Preparing|\u25b6|\u215f|\U0001f3af)/))
    .join('\n')
    .trim()

  if (!cleanContent) return null

  const preview = cleanContent.length > 80
    ? cleanContent.slice(0, 80).replace(/\n/g, ' ') + '...'
    : cleanContent

  return (
    <div className="my-2 rounded-lg overflow-hidden border border-border/50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-accent/5 to-transparent hover:from-accent/10 transition-all text-sm"
      >
        {isStreaming ? (
          <Loader2 size={14} className="text-accent animate-spin" />
        ) : (
          <Brain size={14} className="text-accent" />
        )}
        <span className="text-text-sec font-medium text-xs">Thinking</span>
        {isStreaming && (
          <span className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse" />
        )}
        <ChevronDown
          size={14}
          className={`ml-auto text-text-muted transition-transform duration-200 ${
            expanded ? 'rotate-180' : ''
          }`}
        />
      </button>

      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          expanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="px-3 py-2 bg-elevated/30 border-t border-border/50">
          <div className="text-xs text-text-sec whitespace-pre-wrap font-mono leading-relaxed max-h-[480px] overflow-y-auto">
            {cleanContent}
          </div>
        </div>
      </div>

      {!expanded && (
        <div className="px-3 py-1 text-[10px] text-text-muted/60 truncate font-mono">
          {preview}
        </div>
      )}
    </div>
  )
}
