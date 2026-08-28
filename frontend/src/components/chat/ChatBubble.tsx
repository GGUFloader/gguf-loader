import { User, Bot } from 'lucide-react'
import { MarkdownRenderer } from './MarkdownRenderer'
import { ReasoningBlock } from './ReasoningBlock'
import type { ChatMessage } from '../../stores/chatStore'

interface Props {
  message: ChatMessage
}

export function ChatBubble({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0">
          <Bot size={16} className="text-accent" />
        </div>
      )}

      <div
        className={`max-w-[70%] rounded-2xl px-4 py-3 ${
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
                className={`text-xs px-2 py-1 rounded ${
                  tc.status === 'completed'
                    ? 'bg-green-500/10 text-green-400'
                    : tc.status === 'failed'
                    ? 'bg-red-500/10 text-red-400'
                    : tc.status === 'pending_approval'
                    ? 'bg-yellow-500/10 text-yellow-400'
                    : 'bg-accent/10 text-accent'
                }`}
              >
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
            <MarkdownRenderer content={message.content} />
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-elevated border border-border flex items-center justify-center flex-shrink-0">
          <User size={16} className="text-text-sec" />
        </div>
      )}
    </div>
  )
}
