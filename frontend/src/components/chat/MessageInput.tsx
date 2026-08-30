import { useState, useRef, type KeyboardEvent } from 'react'
import { Send, Square, Paperclip } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { FileMentionPopup } from './FileMentionPopup'
import { ChatAutocomplete, detectTrigger } from './ChatAutocomplete'

export function MessageInput() {
  const [input, setInput] = useState('')
  const [showMentions, setShowMentions] = useState(false)
  const [mentionQuery, setMentionQuery] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { isStreaming, sendMessage, stopStreaming } = useChatStore()

  const [showAutocomplete, setShowAutocomplete] = useState(false)
  const [acTrigger, setAcTrigger] = useState('')
  const [acQuery, setAcQuery] = useState('')

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value
    setInput(val)

    // Detect @ mention (file references)
    const cursorPos = e.target.selectionStart
    const textBeforeCursor = val.slice(0, cursorPos)
    const atMatch = textBeforeCursor.match(/@([\w.\-/]*)$/)
    if (atMatch) {
      setShowMentions(true)
      setMentionQuery(atMatch[1])
      setShowAutocomplete(false)
      return
    } else {
      setShowMentions(false)
    }

    // Detect trigger for autocomplete (@, /, #)
    const trigger = detectTrigger(textBeforeCursor)
    if (trigger) {
      setShowAutocomplete(true)
      setAcTrigger(trigger.trigger)
      setAcQuery(trigger.query)
    } else {
      setShowAutocomplete(false)
    }
  }

  function handleMentionSelect(filePath: string) {
    const cursorPos = textareaRef.current?.selectionStart ?? input.length
    const textBeforeCursor = input.slice(0, cursorPos)
    const textAfterCursor = input.slice(cursorPos)
    const atIndex = textBeforeCursor.lastIndexOf('@')
    const newText = textBeforeCursor.slice(0, atIndex) + `@${filePath} ` + textAfterCursor
    setInput(newText)
    setShowMentions(false)
    textareaRef.current?.focus()
  }

  function handleMentionClose() {
    setShowMentions(false)
    textareaRef.current?.focus()
  }

  function handleAutocompleteSelect(item: any) {
    const cursorPos = textareaRef.current?.selectionStart ?? input.length
    const textBeforeCursor = input.slice(0, cursorPos)
    const textAfterCursor = input.slice(cursorPos)
    // Find the trigger character position
    const triggerIdx = textBeforeCursor.search(/[@/#]\w*$/)
    const newText = textBeforeCursor.slice(0, triggerIdx) + item.insert + ' ' + textAfterCursor
    setInput(newText)
    setShowAutocomplete(false)
    textareaRef.current?.focus()
  }

  function handleAutocompleteClose() {
    setShowAutocomplete(false)
    textareaRef.current?.focus()
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || isStreaming) return
    setInput('')
    setShowMentions(false)
    await sendMessage(text)
  }

  function handleKeyDown(e: KeyboardEvent) {
    // Let popups handle keyboard nav when visible
    if (showMentions || showAutocomplete) {
      return
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="p-4 border-t border-border relative">
      {showMentions && (
        <FileMentionPopup
          query={mentionQuery}
          onSelect={handleMentionSelect}
          onClose={handleMentionClose}
        />
      )}
      {showAutocomplete && (
        <ChatAutocomplete
          query={acQuery}
          trigger={acTrigger}
          onSelect={handleAutocompleteSelect}
          onClose={handleAutocompleteClose}
        />
      )}
      <div className="flex items-end gap-2 bg-elevated border border-border rounded-xl px-4 py-3">
        <button
          className="p-1 text-text-muted hover:text-text transition-colors mb-0.5"
          title="Attach file (use @ in message)"
        >
          <Paperclip size={18} />
        </button>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Type a message... Use @ to mention files"
          rows={1}
          data-chat-input
          aria-label="Chat message input"
          className="flex-1 bg-transparent text-text placeholder-text-muted outline-none resize-none text-sm"
          style={{ minHeight: '24px', maxHeight: '120px' }}
        />
        <button
          onClick={isStreaming ? stopStreaming : handleSend}
          disabled={!input.trim() && !isStreaming}
          className={`p-2 rounded-lg transition-colors ${
            isStreaming
              ? 'bg-danger text-white hover:bg-danger/80'
              : input.trim()
              ? 'bg-accent text-onAccent hover:bg-accent-hover'
              : 'bg-border text-text-muted'
          }`}
        >
          {isStreaming ? <Square size={16} /> : <Send size={16} />}
        </button>
      </div>
      <div className="text-xs text-text-muted text-center mt-2">
        Enter to send · Shift+Enter for newline · @ files · / tools · # models
      </div>
    </div>
  )
}
