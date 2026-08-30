import { useState, useMemo } from 'react'
import { ChevronDown, ChevronRight, FileText } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'

export function ArtifactsSection() {
  const [expanded, setExpanded] = useState(true)
  const { messages } = useChatStore()

  // Extract file references from all assistant messages
  const artifacts = useMemo(() => {
    const files = new Set<string>()
    for (const msg of messages) {
      if (msg.role !== 'assistant') continue
      // Match file patterns from agent output
      const patterns = [
        /(?:wrote?|created?|edited?|modified?|wrote file|created file)\s+[`"']?([\w/.\-]+\.(?:py|js|ts|tsx|jsx|json|md|yaml|yml|toml|cfg|txt|html|css|vue|svelte))[`"']?/gi,
      ]
      for (const pattern of patterns) {
        let match
        while ((match = pattern.exec(msg.content)) !== null) {
          files.add(match[1])
        }
      }
    }
    return Array.from(files)
  }, [messages])

  if (artifacts.length === 0) return null

  return (
    <div className="border-b border-border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-elevated/30 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={14} className="text-text-muted" />
        ) : (
          <ChevronRight size={14} className="text-text-muted" />
        )}
        <span className="text-sm font-medium text-text">Artifacts</span>
        {artifacts.length > 0 && (
          <span className="text-[10px] text-text-muted ml-auto">{artifacts.length}</span>
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-1">
          {artifacts.map((file) => (
            <div key={file} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-elevated/50 transition-colors">
              <FileText size={12} className="text-accent flex-shrink-0" />
              <span className="text-xs text-text-sec truncate font-mono">{file}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
