import { useEffect, useRef, useState, useCallback } from 'react'
import { useChatStore, connectWebSocket } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { ChatBubble } from './ChatBubble'
import { StreamingText } from './StreamingText'
import { StepProgressPanel } from './StepProgressPanel'
import { ReasoningBlock } from './ReasoningBlock'
import { ToolCallCard } from '../agent/ToolCallCard'
import { ToolApprovalDialog } from '../agent/ToolApprovalDialog'
import { PlanTracker } from '../agent/PlanTracker'
import { AgentMetricsBar } from '../agent/AgentMetricsBar'
import { ContextLens } from '../agent/ContextLens'
import { MessageInput } from './MessageInput'
import { Bot, Loader2, ChevronUp, ChevronDown } from 'lucide-react'
import type { ToolApprovalRequest, ChatMessage } from '../../stores/chatStore'

export function ChatPanel() {
  const { messages, isStreaming, streamingText, reasoningBlocks, pendingApprovals, progressSteps, currentAnnouncement } = useChatStore()
  const { agentMode } = useUIStore()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [approvalDialog, setApprovalDialog] = useState<ToolApprovalRequest | null>(null)
  const [activeTurnIndex, setActiveTurnIndex] = useState<number | null>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 150
      if (isNearBottom || isStreaming) {
        el.scrollTop = el.scrollHeight
      }
    }
  }, [messages, streamingText, reasoningBlocks])

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket()
  }, [])

  // Sync agent mode from UI store to chat store
  useEffect(() => {
    useChatStore.getState().setAgentMode(agentMode)
  }, [agentMode])

  // Show approval dialog for first pending approval
  useEffect(() => {
    if (pendingApprovals.length > 0 && !approvalDialog) {
      setApprovalDialog(pendingApprovals[0])
    } else if (pendingApprovals.length === 0) {
      setApprovalDialog(null)
    }
  }, [pendingApprovals, approvalDialog])

  function handleApprove(id: string, approved: boolean) {
    fetch('/api/agent/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ call_id: id, approved }),
    })
    setApprovalDialog(null)
  }

  function handleApproveAll() {
    for (const req of pendingApprovals) {
      handleApprove(req.id, true)
    }
  }

  function handleSkipAll() {
    for (const req of pendingApprovals) {
      handleApprove(req.id, false)
    }
  }

  // Turn navigator — scroll to a specific message
  const scrollToTurn = useCallback((index: number) => {
    const messageEls = scrollRef.current?.querySelectorAll('[data-turn-index]')
    if (messageEls && messageEls[index]) {
      messageEls[index].scrollIntoView({ behavior: 'smooth', block: 'start' })
      setActiveTurnIndex(index)
    }
  }, [])

  // Track active turn on scroll
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const handleScroll = () => {
      const messageEls = el.querySelectorAll('[data-turn-index]')
      for (let i = messageEls.length - 1; i >= 0; i--) {
        const rect = messageEls[i].getBoundingClientRect()
        if (rect.top <= el.getBoundingClientRect().top + 100) {
          setActiveTurnIndex(i)
          break
        }
      }
    }
    el.addEventListener('scroll', handleScroll, { passive: true })
    return () => el.removeEventListener('scroll', handleScroll)
  }, [messages])

  // Separate user turns for the navigator
  const userTurns = messages.reduce<{ msg: ChatMessage; index: number }[]>((acc, msg, i) => {
    if (msg.role === 'user') acc.push({ msg, index: i })
    return acc
  }, [])

  return (
    <div className="h-full flex flex-col relative">
      {/* Approval dialog */}
      {approvalDialog && (
        <ToolApprovalDialog
          request={approvalDialog}
          onApprove={handleApprove}
          onApproveAll={handleApproveAll}
          onSkipAll={handleSkipAll}
          totalPending={pendingApprovals.length}
        />
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <PlanTracker />
        <div className="p-4 space-y-4">
        {messages.length === 0 && !isStreaming ? (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <div className="text-6xl mb-4">🦜</div>
            <h2 className="text-xl font-semibold text-text mb-2">Welcome to GGUF Loader</h2>
            <p className="text-text-muted max-w-md">
              Load a GGUF model from the sidebar to start a conversation.
              {agentMode ? (
                <span className="block mt-2 text-accent">Agent Mode is active — tools are available.</span>
              ) : (
                <span className="block mt-2">Toggle Agent Mode for tool use against your workspace.</span>
              )}
            </p>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <div key={msg.id} data-turn-index={i} className="space-y-2">
                <ChatBubble
                  message={msg}
                  isStreaming={isStreaming && i === messages.length - 1 && msg.role === 'assistant'}
                  onRetry={msg.role === 'assistant' ? () => {
                    // Retry last user message
                    const lastUser = [...messages].reverse().find(m => m.role === 'user')
                    if (lastUser) useChatStore.getState().sendMessage(lastUser.content)
                  } : undefined}
                />
                {/* Inline tool calls */}
                {msg.toolCalls && msg.toolCalls.map((tc, j) => (
                  <ToolCallCard
                    key={j}
                    tool={tc}
                    onApprove={handleApprove}
                  />
                ))}
              </div>
            ))}

            {/* Reasoning blocks */}
            {reasoningBlocks.map((block, i) => (
              <ReasoningBlock key={i} content={block} />
            ))}

            {/* Step progress panel (Codebuff-style) */}
            {progressSteps.length > 0 || currentAnnouncement ? (
              <div className="py-2">
                <StepProgressPanel
                  steps={progressSteps}
                  isStreaming={isStreaming}
                  currentAnnouncement={currentAnnouncement}
                />
              </div>
            ) : (
              /* Live streaming text (fallback when no progress steps) */
              isStreaming && streamingText && (
                <StreamingText content={streamingText} isStreaming={isStreaming} />
              )
            )}
          </>
        )}

        {/* Agent thinking indicator */}
        {isStreaming && !streamingText && (
          <div className="flex items-center gap-3 px-4 py-3">
            <div className="w-8 h-8 rounded-full bg-accent/10 flex items-center justify-center">
              <Bot size={16} className="text-accent" />
            </div>
            <div className="flex items-center gap-2 text-text-muted text-sm">
              <Loader2 size={14} className="animate-spin" />
              <span>Thinking...</span>
            </div>
          </div>
        )}
        </div>
      </div>

      {/* Turn navigator rail — right edge */}
      {userTurns.length > 2 && (
        <div className="absolute right-1 top-4 bottom-20 w-5 flex flex-col items-center gap-0.5 z-10 opacity-60 hover:opacity-100 transition-opacity">
          {/* Nav up */}
          <button
            onClick={() => {
              const prev = activeTurnIndex !== null ? Math.max(0, activeTurnIndex - 1) : 0
              const turn = userTurns.find(t => t.index >= prev)
              if (turn) scrollToTurn(turn.index)
            }}
            className="p-0.5 text-text-muted hover:text-text transition-colors"
          >
            <ChevronUp size={12} />
          </button>

          {/* Turn dots */}
          <div className="flex-1 flex flex-col items-center justify-center gap-1 overflow-hidden">
            {userTurns.map((turn, i) => (
              <button
                key={turn.msg.id}
                onClick={() => scrollToTurn(turn.index)}
                className={`w-2 h-2 rounded-full transition-all ${
                  activeTurnIndex === turn.index
                    ? 'bg-accent scale-125'
                    : 'bg-text-muted/30 hover:bg-text-muted/60'
                }`}
                title={`Turn ${i + 1}: ${turn.msg.content.slice(0, 50)}...`}
              />
            ))}
          </div>

          {/* Nav down */}
          <button
            onClick={() => {
              const next = activeTurnIndex !== null ? Math.min(messages.length - 1, activeTurnIndex + 1) : messages.length - 1
              const turn = [...userTurns].reverse().find(t => t.index <= next)
              if (turn) scrollToTurn(turn.index)
            }}
            className="p-0.5 text-text-muted hover:text-text transition-colors"
          >
            <ChevronDown size={12} />
          </button>
        </div>
      )}

      {/* Context lens + Metrics */}
      <ContextLens />
      <AgentMetricsBar />

      {/* Input */}
      <MessageInput />
    </div>
  )
}
