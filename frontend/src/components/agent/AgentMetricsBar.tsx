import { useEffect, useState } from 'react'
import { Coins, Hash, Clock, Wrench, Zap } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'

export function AgentMetricsBar() {
  const { isStreaming, messages } = useChatStore()
  const [startTime, setStartTime] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [totalTokens, setTotalTokens] = useState(0)
  const [toolCallCount, setToolCallCount] = useState(0)
  const [estimatedCost, setEstimatedCost] = useState(0)

  // Track streaming duration
  useEffect(() => {
    if (isStreaming && !startTime) {
      setStartTime(Date.now())
    } else if (!isStreaming) {
      setStartTime(null)
      setElapsed(0)
    }
  }, [isStreaming, startTime])

  useEffect(() => {
    if (!startTime) return
    const interval = setInterval(() => {
      setElapsed(Date.now() - startTime)
    }, 100)
    return () => clearInterval(interval)
  }, [startTime])

  // Count tokens and tool calls from messages
  useEffect(() => {
    let tokens = 0
    let tools = 0
    for (const msg of messages) {
      // Rough estimate: ~4 chars per token
      tokens += Math.ceil(msg.content.length / 4)
      if (msg.toolCalls) {
        tools += msg.toolCalls.length
      }
    }
    setTotalTokens(tokens)
    setToolCallCount(tools)
    // Rough cost estimate at $0.003/1K tokens (input) + $0.015/1K tokens (output)
    setEstimatedCost((tokens / 1000) * 0.008)
  }, [messages])

  function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  function formatCost(cost: number): string {
    if (cost < 0.01) return `<$0.01`
    return `$${cost.toFixed(2)}`
  }

  if (!isStreaming && messages.length === 0) return null

  return (
    <div className="flex items-center gap-3 px-4 py-1.5 border-t border-border bg-bg/50 text-xs text-text-muted">
      {/* Duration */}
      {isStreaming && (
        <div className="flex items-center gap-1">
          <Clock size={11} />
          <span>{formatDuration(elapsed)}</span>
        </div>
      )}

      {/* Tokens */}
      <div className="flex items-center gap-1">
        <Hash size={11} />
        <span>{totalTokens.toLocaleString()} tokens</span>
      </div>

      {/* Tool calls */}
      {toolCallCount > 0 && (
        <div className="flex items-center gap-1">
          <Wrench size={11} />
          <span>{toolCallCount} tools</span>
        </div>
      )}

      {/* Cost */}
      <div className="flex items-center gap-1">
        <Coins size={11} />
        <span>{formatCost(estimatedCost)}</span>
      </div>

      {/* Streaming indicator */}
      {isStreaming && (
        <div className="flex items-center gap-1 ml-auto text-accent">
          <Zap size={11} className="animate-pulse" />
          <span>Streaming</span>
        </div>
      )}
    </div>
  )
}
