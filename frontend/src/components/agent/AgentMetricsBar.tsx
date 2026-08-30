import { useEffect, useState } from 'react'
import { Coins, Hash, Clock, Wrench, Zap, Database, Activity, TrendingUp } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'

export function AgentMetricsBar() {
  const { isStreaming, messages, agentMetrics } = useChatStore()
  const [startTime, setStartTime] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [totalTokensIn, setTotalTokensIn] = useState(0)
  const [totalTokensOut, setTotalTokensOut] = useState(0)
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
    let tokensIn = 0
    let tokensOut = 0
    let tools = 0
    for (const msg of messages) {
      const chars = msg.content.length
      const tokens = Math.ceil(chars / 4)
      if (msg.role === 'user') {
        tokensIn += tokens
      } else {
        tokensOut += tokens
      }
      if (msg.toolCalls) {
        tools += msg.toolCalls.length
      }
    }
    setTotalTokensIn(tokensIn)
    setTotalTokensOut(tokensOut)
    setToolCallCount(tools)
    // Rough cost estimate (local models = free, API models vary)
    setEstimatedCost((tokensOut / 1000) * 0.015)
  }, [messages])

  function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
  }

  function formatCost(cost: number): string {
    if (cost < 0.001) return 'Free'
    if (cost < 0.01) return `<$0.01`
    return `$${cost.toFixed(3)}`
  }

  function formatTokensPerSec(): string {
    if (elapsed < 500 || totalTokensOut === 0) return '—'
    const tps = totalTokensOut / (elapsed / 1000)
    return `${tps.toFixed(1)} t/s`
  }

  function formatCacheHit(): string {
    // Simulated — real data comes from WebSocket events
    return '—'
  }

  // Use server-reported duration when generation is complete
  const displayDuration = !isStreaming && agentMetrics.durationMs > 0
    ? agentMetrics.durationMs : elapsed

  if (!isStreaming && messages.length === 0) return null

  const totalTokens = totalTokensIn + totalTokensOut

  return (
    <div className="flex items-center gap-4 px-4 py-1.5 border-t border-border bg-bg/50 text-xs text-text-muted select-none">
      {/* Duration */}
      {displayDuration > 0 && (
        <div className="flex items-center gap-1" title="Elapsed time">
          <Clock size={11} />
          <span>{formatDuration(displayDuration)}</span>
        </div>
      )}

      {/* Total tokens */}
      <div className="flex items-center gap-1" title={`${totalTokensIn.toLocaleString()} in / ${totalTokensOut.toLocaleString()} out`}>
        <Hash size={11} />
        <span>{totalTokens.toLocaleString()} tok</span>
      </div>

      {/* Tokens/sec (decode speed) */}
      {isStreaming && (
        <div className="flex items-center gap-1 text-accent" title="Decode speed">
          <Activity size={11} />
          <span>{formatTokensPerSec()}</span>
        </div>
      )}

      {/* Cache hit rate */}
      <div className="flex items-center gap-1" title="Prompt cache hit rate">
        <Database size={11} />
        <span>Cache {formatCacheHit()}</span>
      </div>

      {/* Tool calls */}
      {(toolCallCount > 0 || agentMetrics.toolCalls > 0) && (
        <div className="flex items-center gap-1" title={`${agentMetrics.toolCalls || toolCallCount} tool calls (${agentMetrics.toolSuccesses || 0} succeeded)`}>
          <Wrench size={11} />
          <span>{agentMetrics.toolCalls || toolCallCount} tools</span>
          {agentMetrics.toolSuccesses > 0 && agentMetrics.toolSuccesses < (agentMetrics.toolCalls || toolCallCount) && (
            <span className="text-green-400">✓{agentMetrics.toolSuccesses}</span>
          )}
        </div>
      )}

      {/* Cost */}
      <div className="flex items-center gap-1" title="Estimated cost">
        <Coins size={11} />
        <span>{formatCost(estimatedCost)}</span>
      </div>

      {/* Preset badge */}
      {agentMetrics.preset && (
        <div className="flex items-center gap-1 text-accent/70" title="Active agent preset">
          <Zap size={11} />
          <span>{agentMetrics.preset}</span>
        </div>
      )}

      {/* Tokens breakdown tooltip */}
      <div
        className="ml-auto flex items-center gap-1 text-text-muted/60"
        title={`Input: ${totalTokensIn.toLocaleString()} tokens\nOutput: ${totalTokensOut.toLocaleString()} tokens\nSteps: ${messages.filter(m => m.toolCalls?.length).length}`}
      >
        <TrendingUp size={11} />
        <span>↑{totalTokensIn.toLocaleString()} ↓{totalTokensOut.toLocaleString()}</span>
      </div>

      {/* Streaming indicator */}
      {isStreaming && (
        <div className="flex items-center gap-1 text-accent">
          <Zap size={11} className="animate-pulse" />
          <span>Generating</span>
        </div>
      )}
    </div>
  )
}
