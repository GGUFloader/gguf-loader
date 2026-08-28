import { useEffect, useRef } from 'react'
import { MarkdownRenderer } from './MarkdownRenderer'
import { Bot } from 'lucide-react'

interface Props {
  content: string
  isStreaming: boolean
}

export function StreamingText({ content, isStreaming }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (ref.current) {
      const el = ref.current
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
      if (isNearBottom) {
        el.scrollTop = el.scrollHeight
      }
    }
  }, [content])

  if (!content && !isStreaming) return null

  return (
    <div ref={ref} className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0 mt-1">
        <Bot size={16} className="text-accent" />
      </div>
      <div className="max-w-[75%]">
        <div className="rounded-2xl px-4 py-3 bg-elevated border border-border">
          <div className="prose prose-invert prose-sm max-w-none">
            <MarkdownRenderer content={content} />
          </div>
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-accent ml-1 animate-pulse rounded-sm" />
          )}
        </div>
      </div>
    </div>
  )
}
