import { useState } from 'react'
import { User, Bot, Copy, Check, ChevronDown, ChevronUp, Loader2, AlertCircle, RotateCcw } from 'lucide-react'
import { MarkdownRenderer } from './MarkdownRenderer'
import { ReasoningBlock } from './ReasoningBlock'
import type { ChatMessage } from '../../stores/chatStore'

interface Props {
  message: ChatMessage
  isStreaming?: boolean
  onRetry?: () => void
}

const TRUNCATE_THRESHOLD = 800 // chars before truncation

export function ChatBubble({ message, isStreaming: _isStreaming = false, onRetry }: Props) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const shouldTruncate = !isUser && message.content.length > TRUNCATE_THRESHOLD
  const displayContent = shouldTruncate && !expanded
    ? message.content.slice(0, TRUNCATE_THRESHOLD)
    : message.content

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`flex gap-3 group ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0 mt-1">
          <Bot size={16} className="text-accent" />
        </div>
      )}

      <div className={`max-w-[75%] relative ${isUser ? 'order-1' : ''}`}>
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-accent text-onAccent'
              : 'bg-elevated border border-border text-text'
          }`}
        >
          {/* Thinking block */}
          {message.thinking && (
            <ReasoningBlock content={message.thinking} />
          )}

          {/* Tool calls */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mb-2 space-y-1">
              {message.toolCalls.map((tc, i) => (
                <div
                  key={i}
                  className={`text-xs px-2 py-1 rounded flex items-center gap-1.5 ${
                    tc.status === 'completed'
                      ? 'bg-green-500/10 text-green-400'
                      : tc.status === 'failed'
                      ? 'bg-red-500/10 text-red-400'
                      : tc.status === 'pending_approval'
                      ? 'bg-yellow-500/10 text-yellow-400'
                      : 'bg-accent/10 text-accent'
                  }`}
                >
                  {tc.status === 'running' && <Loader2 size={10} className="animate-spin" />}
                  {tc.status === 'completed' && <Check size={10} />}
                  {tc.status === 'failed' && <AlertCircle size={10} />}
                  🔧 {tc.name}
                  {tc.status === 'pending_approval' && ' (awaiting approval)'}
                </div>
              ))}
            </div>
          )}

          {/* Message content */}
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none">
              <MarkdownRenderer content={displayContent} />
            </div>
          )}

          {/* Truncation indicator */}
          {shouldTruncate && !expanded && (
            <button
              onClick={() => setExpanded(true)}
              className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover mt-2 transition-colors"
            >
              <ChevronDown size={12} />
              Show {message.content.length - TRUNCATE_THRESHOLD} more characters
            </button>
          )}

          {/* Collapse button when expanded */}
          {shouldTruncate && expanded && (
            <button
              onClick={() => setExpanded(false)}
              className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover mt-2 transition-colors"
            >
              <ChevronUp size={12} />
              Collapse
            </button>
          )}
        </div>

        {/* Action buttons — visible on hover */}
        {!isUser && message.content && (
          <div className="absolute -right-8 top-2 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col gap-1">
            <button
              onClick={handleCopy}
              className="p-1 rounded bg-elevated border border-border text-text-muted hover:text-text transition-colors"
              title="Copy message"
            >
              {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
            </button>
            {onRetry && (
              <button
                onClick={onRetry}
                className="p-1 rounded bg-elevated border border-border text-text-muted hover:text-text transition-colors"
                title="Retry"
              >
                <RotateCcw size={12} />
              </button>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-elevated border border-border flex items-center justify-center flex-shrink-0 mt-1">
          <User size={16} className="text-text-sec" />
        </div>
      )}
    </div>
  )
}
