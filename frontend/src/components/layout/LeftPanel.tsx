import { useEffect, useState, useCallback } from 'react'
import {
  Plus,
  Search,
  FolderOpen,
  MessageSquare,
  MoreVertical,
  GitFork,
  Pencil,
  Trash2,
  X,
  Bot,
  Cpu,
  XCircle,
} from 'lucide-react'
import { sessionApi, modelApi } from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { ModelLoadDialog } from '../model/ModelLoadDialog'
import type { SessionInfo, ModelInfo } from '../../api/types'

export function LeftPanel() {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [activeSession, setActiveSession] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<string | null>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)
  const { clearMessages } = useChatStore()
  const [showLoadDialog, setShowLoadDialog] = useState(false)

  const loadSessions = useCallback(async () => {
    try {
      const data = await sessionApi.list()
      setSessions(data)
    } catch {}
    setLoading(false)
  }, [])

  const loadModelInfo = useCallback(async () => {
    try {
      const data = await modelApi.info()
      setModelInfo(data)
    } catch {}
  }, [])

  useEffect(() => {
    loadSessions()
    loadModelInfo()
  }, [loadSessions, loadModelInfo])

  async function handleNewChat() {
    try {
      const session = await sessionApi.create('New Chat')
      setSessions((prev) => [session, ...prev])
      setActiveSession(session.id)
      clearMessages()
    } catch {}
  }

  async function handleDeleteSession(id: string) {
    try {
      await sessionApi.delete(id)
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (activeSession === id) setActiveSession(null)
    } catch {}
    setContextMenu(null)
  }

  async function handleForkSession(id: string) {
    try {
      const forked = await sessionApi.fork(id)
      setSessions((prev) => [forked, ...prev])
      setActiveSession(forked.id)
    } catch {}
    setContextMenu(null)
  }

  function startRename(session: SessionInfo) {
    setRenamingId(session.id)
    setRenameValue(session.title || '')
    setContextMenu(null)
  }

  async function confirmRename(id: string) {
    if (renameValue.trim()) {
      try {
        await sessionApi.get(id) // endpoint exists, title update would need a PUT
        setSessions((prev) =>
          prev.map((s) => (s.id === id ? { ...s, title: renameValue.trim() } : s))
        )
      } catch {}
    }
    setRenamingId(null)
  }

  const filtered = sessions.filter(
    (s) => !search || s.title?.toLowerCase().includes(search.toLowerCase())
  )

  function formatDate(dateStr: string) {
    const d = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 60_000) return 'just now'
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
    return d.toLocaleDateString()
  }

  return (
    <div className="w-64 h-full flex flex-col bg-surface border-r border-border">
      {/* Quick actions */}
      <div className="p-3 space-y-2 border-b border-border">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 bg-accent text-onAccent rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
        >
          <Plus size={16} />
          New Chat
        </button>
        <div className="flex gap-2">
          <button
            onClick={() => setShowLoadDialog(true)}
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 bg-elevated border border-border rounded-lg text-xs text-text-sec hover:border-accent transition-colors"
          >
            <FolderOpen size={12} />
            Load Model
          </button>
        </div>
      </div>

      {/* Model info */}
      {modelInfo && modelInfo.loaded && (
        <div className="px-3 py-2 border-b border-border">
          <div className="flex items-center gap-2 px-2 py-1.5 bg-elevated rounded-lg">
            <div className="w-2 h-2 rounded-full bg-success" />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-text truncate">
                {modelInfo.filename}
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-text-muted">
                {modelInfo.family && <span>{modelInfo.family}</span>}
                {modelInfo.quantization && <span>· {modelInfo.quantization}</span>}
                {modelInfo.gpu && (
                  <span className="flex items-center gap-0.5 text-accent">
                    <Cpu size={9} /> GPU
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={async () => {
                await modelApi.unload()
                setModelInfo(null)
              }}
              className="p-0.5 text-text-muted hover:text-red-400 transition-colors"
              title="Unload model"
            >
              <XCircle size={12} />
            </button>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 px-2 py-1.5 bg-elevated border border-border rounded-lg">
          <Search size={14} className="text-text-muted" />
          <input
            type="text"
            placeholder="Search chats..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-transparent text-sm text-text placeholder-text-muted outline-none w-full"
          />
          {search && (
            <button onClick={() => setSearch('')} className="text-text-muted hover:text-text">
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 space-y-0.5">
        {loading ? (
          <div className="text-center text-text-muted text-sm py-8">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center text-text-muted text-sm py-8">
            {search ? 'No matching chats' : 'No sessions yet'}
          </div>
        ) : (
          filtered.map((session) => (
            <div key={session.id} className="relative">
              {renamingId === session.id ? (
                <div className="flex items-center gap-1 px-2 py-1.5">
                  <input
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') confirmRename(session.id)
                      if (e.key === 'Escape') setRenamingId(null)
                    }}
                    onBlur={() => confirmRename(session.id)}
                    className="flex-1 bg-elevated border border-accent rounded px-2 py-1 text-xs text-text outline-none"
                  />
                </div>
              ) : (
                <button
                  onClick={() => {
                    setActiveSession(session.id)
                    // Load session messages would go here
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault()
                    setContextMenu(contextMenu === session.id ? null : session.id)
                  }}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors group ${
                    activeSession === session.id
                      ? 'bg-accent/10 border border-accent/30'
                      : 'hover:bg-elevated border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <MessageSquare size={13} className="flex-shrink-0 text-text-muted" />
                    <span className="text-sm text-text truncate flex-1">
                      {session.title || 'Untitled session'}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setContextMenu(contextMenu === session.id ? null : session.id)
                      }}
                      className="p-0.5 opacity-0 group-hover:opacity-100 text-text-muted hover:text-text transition-all"
                    >
                      <MoreVertical size={12} />
                    </button>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 pl-5">
                    <span className="text-[10px] text-text-muted">
                      {session.message_count} msgs
                    </span>
                    <span className="text-[10px] text-text-muted">
                      {formatDate(session.updated)}
                    </span>
                  </div>
                </button>
              )}

              {/* Context menu */}
              {contextMenu === session.id && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setContextMenu(null)}
                  />
                  <div className="absolute right-2 top-8 w-36 bg-elevated border border-border rounded-lg shadow-xl z-50 overflow-hidden">
                    <button
                      onClick={() => startRename(session)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text hover:bg-elevated/80 transition-colors"
                    >
                      <Pencil size={12} />
                      Rename
                    </button>
                    <button
                      onClick={() => handleForkSession(session.id)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text hover:bg-elevated/80 transition-colors"
                    >
                      <GitFork size={12} />
                      Fork
                    </button>
                    <div className="border-t border-border" />
                    <button
                      onClick={() => handleDeleteSession(session.id)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      <Trash2 size={12} />
                      Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>

      {/* Model load dialog */}
      {showLoadDialog && (
        <ModelLoadDialog
          onClose={() => setShowLoadDialog(false)}
          onLoaded={(info) => {
            setModelInfo(info)
            loadSessions()
          }}
        />
      )}

      {/* Footer */}
      <div className="px-3 py-2 border-t border-border">
        <div className="flex items-center gap-2 text-[10px] text-text-muted">
          <Bot size={11} />
          <span>GGUF Loader v1.0</span>
        </div>
      </div>
    </div>
  )
}
