import { useEffect, useRef, useState } from 'react'
import { useChatStore, connectWebSocket } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { ChatBubble } from './ChatBubble'
import { StreamingText } from './StreamingText'
import { ReasoningBlock } from './ReasoningBlock'
import { ToolCallCard } from '../agent/ToolCallCard'
import { ToolApprovalDialog } from '../agent/ToolApprovalDialog'
import { AgentMetricsBar } from '../agent/AgentMetricsBar'
import { ContextLens } from '../agent/ContextLens'
import { MessageInput } from './MessageInput'
import { Bot, Loader2 } from 'lucide-react'
import type { ToolApprovalRequest } from '../../stores/chatStore'

export function ChatPanel() {
  const { messages, isStreaming, streamingText, reasoningBlocks, pendingApprovals } = useChatStore()
  const { agentMode } = useUIStore()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [approvalDialog, setApprovalDialog] = useState<ToolApprovalRequest | null>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamingText, reasoningBlocks])

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket()
  }, [])

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

  return (
    <div className="h-full flex flex-col">
      {/* Approval dialog */}
      {approvalDialog && (
        <ToolApprovalDialog
          request={approvalDialog}
          onApprove={handleApprove}
        />
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
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
            {messages.map((msg) => (
              <div key={msg.id} className="space-y-2">
                <ChatBubble message={msg} />
                {/* Inline tool calls */}
                {msg.toolCalls && msg.toolCalls.map((tc, i) => (
                  <ToolCallCard
                    key={i}
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

            {/* Live streaming text */}
            {isStreaming && streamingText && (
              <StreamingText content={streamingText} isStreaming={isStreaming} />
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

      {/* Context lens + Metrics */}
      <ContextLens />
      <AgentMetricsBar />

      {/* Input */}
      <MessageInput />
    </div>
  )
}
