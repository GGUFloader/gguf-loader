import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, FolderOpen, Plug, FileText, Globe } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'

export function ContextSection() {
  const [expanded, setExpanded] = useState(true)
  const [workspace, setWorkspace] = useState('')
  const { messages } = useChatStore()

  useEffect(() => {
    try {
      const saved = localStorage.getItem('ggufloader_settings')
      if (saved) {
        const s = JSON.parse(saved)
        if (s.workspace) setWorkspace(s.workspace)
      }
    } catch {}
  }, [])

  // Extract recently worked files from messages
  const workingFiles = (() => {
    const files = new Set<string>()
    for (const msg of [...messages].reverse().slice(0, 10)) {
      if (msg.role !== 'assistant') continue
      const patterns = [
        /(?:wrote?|created?|edited?|modified?|reading|reading file)\s+[`"']?([\w/.\-]+\.(?:py|js|ts|tsx|jsx|json|md|yaml|yml))[`"']?/gi,
      ]
      for (const pattern of patterns) {
        let match
        while ((match = pattern.exec(msg.content)) !== null) {
          files.add(match[1])
        }
      }
    }
    return Array.from(files).slice(0, 8)
  })()

  const hasContent = workspace || workingFiles.length > 0

  if (!hasContent) return null

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
        <span className="text-sm font-medium text-text">Context</span>
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-3">
          {/* Selected folders */}
          {workspace && (
            <div>
              <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Selected folders</div>
              <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-elevated/50">
                <FolderOpen size={12} className="text-accent flex-shrink-0" />
                <span className="text-xs text-text-sec truncate">{workspace.split(/[/\\]/).pop()}</span>
              </div>
            </div>
          )}

          {/* Connectors */}
          <div>
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Connectors</div>
            <div className="space-y-1">
              <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg">
                <Globe size={12} className="text-text-muted flex-shrink-0" />
                <span className="text-xs text-text-sec">Web search</span>
              </div>
              <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg">
                <Plug size={12} className="text-text-muted flex-shrink-0" />
                <span className="text-xs text-text-sec">Local tools</span>
              </div>
            </div>
          </div>

          {/* Working files */}
          {workingFiles.length > 0 && (
            <div>
              <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Working files</div>
              <div className="space-y-0.5">
                {workingFiles.map((file) => (
                  <div key={file} className="flex items-center gap-2 px-2 py-1 rounded-lg">
                    <FileText size={11} className="text-text-muted flex-shrink-0" />
                    <span className="text-[11px] text-text-sec truncate font-mono">{file.split('/').pop()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
