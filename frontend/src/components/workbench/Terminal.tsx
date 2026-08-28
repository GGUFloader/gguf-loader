import { useState, useRef, useEffect } from 'react'
import { Terminal as TerminalIcon, Send, Trash2, Loader2 } from 'lucide-react'

interface TerminalLine {
  type: 'input' | 'output' | 'error'
  content: string
  timestamp: number
}

export function Terminal() {
  const [lines, setLines] = useState<TerminalLine[]>([])
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [running, setRunning] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [lines])

  async function runCommand(cmd: string) {
    if (!cmd.trim()) return

    // Add input line
    setLines((prev) => [
      ...prev,
      { type: 'input', content: `$ ${cmd}`, timestamp: Date.now() },
    ])
    setHistory((prev) => [...prev, cmd])
    setHistoryIndex(-1)
    setInput('')
    setRunning(true)

    try {
      const res = await fetch('/api/files/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
      })
      const data = await res.json()

      if (data.stdout) {
        setLines((prev) => [
          ...prev,
          { type: 'output', content: data.stdout, timestamp: Date.now() },
        ])
      }
      if (data.stderr) {
        setLines((prev) => [
          ...prev,
          { type: 'error', content: data.stderr, timestamp: Date.now() },
        ])
      }
      if (!data.stdout && !data.stderr) {
        setLines((prev) => [
          ...prev,
          { type: 'output', content: '(no output)', timestamp: Date.now() },
        ])
      }
    } catch (e: any) {
      setLines((prev) => [
        ...prev,
        { type: 'error', content: `Error: ${e.message}`, timestamp: Date.now() },
      ])
    }

    setRunning(false)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !running) {
      runCommand(input)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (history.length > 0) {
        const newIndex = historyIndex === -1 ? history.length - 1 : Math.max(0, historyIndex - 1)
        setHistoryIndex(newIndex)
        setInput(history[newIndex])
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (historyIndex >= 0) {
        const newIndex = historyIndex + 1
        if (newIndex >= history.length) {
          setHistoryIndex(-1)
          setInput('')
        } else {
          setHistoryIndex(newIndex)
          setInput(history[newIndex])
        }
      }
    } else if (e.key === 'l' && e.ctrlKey) {
      e.preventDefault()
      setLines([])
    }
  }

  function clearTerminal() {
    setLines([])
  }

  return (
    <div className="h-full flex flex-col bg-bg">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border">
        <TerminalIcon size={12} className="text-accent" />
        <span className="text-xs font-medium text-text flex-1">Terminal</span>
        <button
          onClick={clearTerminal}
          className="p-1 text-text-muted hover:text-text rounded transition-colors"
          title="Clear"
        >
          <Trash2 size={11} />
        </button>
      </div>

      {/* Output */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-3 py-2 font-mono text-xs"
      >
        {lines.length === 0 && (
          <div className="text-text-muted py-4 text-center">
            Type a command and press Enter
          </div>
        )}

        {lines.map((line, i) => (
          <div
            key={i}
            className={`py-0.5 whitespace-pre-wrap break-all ${
              line.type === 'input'
                ? 'text-accent font-medium'
                : line.type === 'error'
                ? 'text-red-400'
                : 'text-text-sec'
            }`}
          >
            {line.content}
          </div>
        ))}

        {running && (
          <div className="flex items-center gap-1.5 py-1 text-accent">
            <Loader2 size={11} className="animate-spin" />
            <span>Running...</span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 px-3 py-2 border-t border-border">
        <span className="text-accent text-xs font-mono">$</span>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter command..."
          className="flex-1 bg-transparent text-xs text-text placeholder-text-muted outline-none font-mono"
          disabled={running}
        />
        <button
          onClick={() => runCommand(input)}
          disabled={!input.trim() || running}
          className="p-1 text-text-muted hover:text-accent disabled:opacity-30 transition-colors"
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  )
}
