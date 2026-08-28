import { useEffect, useRef } from 'react'

interface Props {
  content: string
  isStreaming: boolean
}

export function StreamingText({ content, isStreaming }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight
    }
  }, [content])

  if (!content && !isStreaming) return null

  return (
    <div ref={ref} className="relative">
      <span className="whitespace-pre-wrap">{content}</span>
      {isStreaming && (
        <span className="inline-block w-2 h-4 bg-accent ml-0.5 animate-pulse" />
      )}
    </div>
  )
}
