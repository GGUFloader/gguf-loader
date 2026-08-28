import { useMemo } from 'react'
import { useChatStore } from '../../stores/chatStore'

const TOKEN_BUDGET = 32768 // default context length

const SEGMENTS = [
  { key: 'system', label: 'System', color: '#6366f1' },
  { key: 'history', label: 'History', color: '#3b82f6' },
  { key: 'tools', label: 'Tools', color: '#f59e0b' },
  { key: 'response', label: 'Response', color: '#22c55e' },
  { key: 'free', label: 'Free', color: '#374151' },
]

export function ContextLens() {
  const { messages } = useChatStore()

  const breakdown = useMemo(() => {
    // Estimate token usage from messages
    let systemTokens = 0
    let historyTokens = 0
    let toolTokens = 0

    for (const msg of messages) {
      const est = Math.ceil(msg.content.length / 4)
      if (msg.role === 'system') {
        systemTokens += est
      } else {
        historyTokens += est
      }
      if (msg.toolCalls) {
        for (const tc of msg.toolCalls) {
          toolTokens += Math.ceil(JSON.stringify(tc.args).length / 4)
          if (tc.result) toolTokens += Math.ceil(tc.result.length / 4)
        }
      }
    }

    // Reserve ~2K for system prompt if not already in messages
    if (systemTokens === 0) systemTokens = 2048

    const used = systemTokens + historyTokens + toolTokens
    const responseTokens = Math.min(4096, Math.max(0, TOKEN_BUDGET - used))
    const free = Math.max(0, TOKEN_BUDGET - used - responseTokens)

    return {
      system: systemTokens,
      history: historyTokens,
      tools: toolTokens,
      response: responseTokens,
      free,
      total: TOKEN_BUDGET,
      used,
    }
  }, [messages])

  const usedPercent = Math.min(100, (breakdown.used / breakdown.total) * 100)

  return (
    <div className="px-4 py-1.5 border-t border-border bg-bg/30">
      {/* Bar */}
      <div className="h-1.5 rounded-full overflow-hidden flex bg-border/30 mb-1">
        {SEGMENTS.map((seg) => {
          const tokens = breakdown[seg.key as keyof typeof breakdown]
          if (typeof tokens !== 'number' || tokens <= 0) return null
          const width = (tokens / breakdown.total) * 100
          return (
            <div
              key={seg.key}
              style={{ width: `${width}%`, backgroundColor: seg.color }}
              className="h-full transition-all duration-300"
              title={`${seg.label}: ${tokens.toLocaleString()} tokens`}
            />
          )
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 text-[10px] text-text-muted">
        {SEGMENTS.map((seg) => {
          const tokens = breakdown[seg.key as keyof typeof breakdown]
          if (typeof tokens !== 'number' || tokens <= 0) return null
          return (
            <div key={seg.key} className="flex items-center gap-1">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: seg.color }}
              />
              <span>{seg.label}</span>
              <span className="text-text-sec">{Math.round(tokens / 1000)}K</span>
            </div>
          )
        })}
        <div className="ml-auto text-text-sec">
          {usedPercent.toFixed(0)}% used
        </div>
      </div>
    </div>
  )
}
