import { useEffect, useRef, useState } from 'react'
import { useChatStore, connectWebSocket } from '../../stores/chatStore'
import { startModelRefresh, stopModelRefresh } from '../../stores/modelStore'
import { useUIStore } from '../../stores/uiStore'
import { ChatBubble } from './ChatBubble'
import { StreamingText } from './StreamingText'
import { StepProgressPanel } from './StepProgressPanel'
import { ToolCallCard } from '../agent/ToolCallCard'
import { ToolApprovalDialog } from '../agent/ToolApprovalDialog'
import { MessageInput } from './MessageInput'
import { Loader2 } from 'lucide-react'
import type { ToolApprovalRequest } from '../../stores/chatStore'

export function ChatPanel() {
  const { messages, isStreaming, streamingText, pendingApprovals, progressSteps, currentAnnouncement } = useChatStore()
  const { agentMode } = useUIStore()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [approvalDialog, setApprovalDialog] = useState<ToolApprovalRequest | null>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 150
      if (isNearBottom || isStreaming) {
        el.scrollTop = el.scrollHeight
      }
    }
  }, [messages, streamingText, progressSteps])

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket()
    // Poll model info so the header chip reflects the startup auto-load.
    startModelRefresh()
    return () => stopModelRefresh()
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

      {/* Messages — centered column */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="max-w-[720px] mx-auto px-4 py-6 space-y-4">
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
              {messages.map((msg, i) => {
                const isLast = i === messages.length - 1
                // Codebuff-style turns: each assistant reply carries the
                // process that produced it. While a run is live the panel
                // streams from the global progress list; once the run
                // completes the steps are folded into msg.steps (see
                // message_complete in chatStore) so they stay attached to
                // that reply instead of living in a side panel.
                const isLiveAssistant = msg.role === 'assistant' &&
                  isLast && isStreaming && msg.id === useChatStore.getState().currentStreamingId
                const hasLiveSteps = progressSteps.length > 0 || !!currentAnnouncement

                return (
                  <div key={msg.id} className="space-y-2">
                    {/* Inline tool calls */}
                    {msg.toolCalls && msg.toolCalls.map((tc, j) => (
                      <ToolCallCard
                        key={j}
                        tool={tc}
                        onApprove={handleApprove}
                      />
                    ))}
                    {/* Process shown above the reply text, like Codebuff */}
                    {msg.steps && msg.steps.length > 0 ? (
                      <div className="py-1">
                        <StepProgressPanel
                          steps={msg.steps}
                          isStreaming={false}
                        />
                      </div>
                    ) : isLiveAssistant && hasLiveSteps ? (
                      <div className="py-1">
                        <StepProgressPanel
                          steps={progressSteps}
                          isStreaming={isStreaming}
                          currentAnnouncement={currentAnnouncement}
                        />
                      </div>
                    ) : null}

                    {/* While a run is live: stream tokens as they arrive (the
                        finished bubble + folded steps appear on
                        message_complete). Never render the still-empty
                        assistant bubble mid-run. */}
                    {isLiveAssistant ? (
                      streamingText ? (
                        <StreamingText content={streamingText} isStreaming={isStreaming} />
                      ) : (
                        <div className="flex items-center gap-2 py-1">
                          <Loader2 size={14} className="text-accent animate-spin" />
                          <span className="text-sm text-text-muted">Working...</span>
                        </div>
                      )
                    ) : (
                      <ChatBubble
                        message={msg}
                        isStreaming={false}
                        onRetry={msg.role === 'assistant' ? () => {
                          const lastUser = [...messages].reverse().find(m => m.role === 'user')
                          if (lastUser) useChatStore.getState().sendMessage(lastUser.content)
                        } : undefined}
                      />
                    )}
                  </div>
                )
              })}
            </>
          )}
        </div>
      </div>

      {/* Input */}
      <MessageInput />
    </div>
  )
}
