import { useState, useEffect } from 'react'
import { X, Copy, Check, Loader2, FileText } from 'lucide-react'
import { filesApi } from '../../api/client'

interface Props {
  filePath: string
  onClose: () => void
}

export function FileViewer({ filePath, onClose }: Props) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    loadFile()
  }, [filePath])

  async function loadFile() {
    setLoading(true)
    setError(null)
    try {
      const data = await filesApi.content(filePath)
      setContent(data.content || '')
    } catch (e: any) {
      setError(e.message || 'Failed to load file')
    }
    setLoading(false)
  }

  function handleCopy() {
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const filename = filePath.split(/[/\\]/).pop() || filePath
  const lines = content.split('\n')

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-elevated/30">
        <FileText size={13} className="text-accent flex-shrink-0" />
        <span className="text-xs font-medium text-text truncate flex-1">{filename}</span>
        <span className="text-[10px] text-text-muted flex-shrink-0">{lines.length} lines</span>
        <button
          onClick={handleCopy}
          className="p-1 text-text-muted hover:text-text rounded transition-colors"
          title="Copy content"
        >
          {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
        </button>
        <button
          onClick={onClose}
          className="p-1 text-text-muted hover:text-text rounded transition-colors"
          title="Close"
        >
          <X size={12} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 size={16} className="animate-spin text-text-muted" />
          </div>
        ) : error ? (
          <div className="p-4 text-center text-red-400 text-xs">{error}</div>
        ) : (
          <pre className="text-xs font-mono">
            {lines.map((line, i) => (
              <div key={i} className="flex hover:bg-elevated/30">
                <span className="w-10 flex-shrink-0 text-right pr-3 text-text-muted/50 select-none py-0.5">
                  {i + 1}
                </span>
                <span className="flex-1 pr-4 py-0.5 whitespace-pre text-text-sec">{line}</span>
              </div>
            ))}
          </pre>
        )}
      </div>
    </div>
  )
}
