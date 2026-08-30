import { useState, useMemo } from 'react'
import { Copy, Check, ChevronDown, ChevronUp, FileText } from 'lucide-react'
import { MarkdownRenderer } from './MarkdownRenderer'
import type { ChatMessage } from '../../stores/chatStore'

interface Props {
  message: ChatMessage
  isStreaming?: boolean
  onRetry?: () => void
}

const TRUNCATE_THRESHOLD = 800

// Extract file references from message content
function extractFileRefs(content: string): string[] {
  const files = new Set<string>()
  const patterns = [
    /(?:wrote?|created?|edited?|modified?|read|listed?)\s+(?:file\s+)?[`"']?([\w/.\-]+\.(?:py|js|ts|tsx|jsx|json|md|yaml|yml|toml|cfg|txt|html|css))[`"']?/gi,
    /([\w/.\-]+\.(?:py|js|ts|tsx|jsx|json|md|yaml|yml|toml|cfg|txt|html|css))(?:\s|$|,|\))/g,
  ]
  for (const pattern of patterns) {
    let match
    while ((match = pattern.exec(content)) !== null) {
      const f = match[1]
      if (f && !f.startsWith('http') && f.length < 100) files.add(f)
    }
  }
  return Array.from(files).slice(0, 5)
}

export function ChatBubble({ message, isStreaming: _isStreaming = false, onRetry }: Props) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const fileRefs = useMemo(
    () => isUser ? [] : extractFileRefs(message.content),
    [message.content, isUser]
  )

  const shouldTruncate = !isUser && message.content.length > TRUNCATE_THRESHOLD
  const displayContent = shouldTruncate && !expanded
    ? message.content.slice(0, TRUNCATE_THRESHOLD)
    : message.content

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // User messages — right-aligned, accent background
  if (isUser) {
    return (
      <div className="flex justify-end group">
        <div className="max-w-[80%] relative">
          <div className="bg-accent text-onAccent rounded-2xl px-4 py-3">
            <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</div>
          </div>
          {/* Copy button on hover */}
          <div className="absolute -left-8 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={handleCopy}
              className="p-1 rounded bg-elevated border border-border text-text-muted hover:text-text transition-colors"
              title="Copy message"
            >
              {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Assistant messages — left-aligned, no background, clean text
  return (
    <div className="flex justify-start group">
      <div className="max-w-[80%] relative">
        <div className="text-text">
          {/* Message content */}
          <div className="prose prose-invert prose-sm max-w-none">
            <MarkdownRenderer content={displayContent} />
          </div>

          {/* File reference chips */}
          {fileRefs.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-border/30">
              {fileRefs.map((file) => (
                <span
                  key={file}
                  className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-accent/5 border border-accent/20 text-accent/80 font-mono"
                >
                  <FileText size={9} />
                  {file.split('/').pop()}
                </span>
              ))}
            </div>
          )}

          {/* Truncation */}
          {shouldTruncate && !expanded && (
            <button
              onClick={() => setExpanded(true)}
              className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover mt-2 transition-colors"
            >
              <ChevronDown size={12} />
              Show more ({message.content.length - TRUNCATE_THRESHOLD} chars)
            </button>
          )}
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

        {/* Action buttons on hover */}
        {message.content && (
          <div className="absolute -right-8 top-0 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col gap-1">
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
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 1 3.5-7.1"/><polyline points="3 2 3 8 9 8"/></svg>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
