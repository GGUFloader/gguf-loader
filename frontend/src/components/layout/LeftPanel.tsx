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
  Code,
  Users,
  HardDrive,
  Loader2,
  Zap,
} from 'lucide-react'
import { sessionApi, modelApi } from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { ModelLoadDialog } from '../model/ModelLoadDialog'
import type { SessionInfo, ModelInfo } from '../../api/types'
import { FileExplorer } from '../workbench/FileExplorer'

type LeftTab = 'chat' | 'code' | 'cowork'

export function LeftPanel() {
  const [leftTab, setLeftTab] = useState<LeftTab>('chat')
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [activeSession, setActiveSession] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<string | null>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)
  const { clearMessages, setActiveSessionId } = useChatStore()
  const [showLoadDialog, setShowLoadDialog] = useState(false)
  const workspace = useWorkspaceStore((s) => s.workspace)
  const [modelFolder, setModelFolder] = useState('')
  const [folderModels, setFolderModels] = useState<any[]>([])
  const [folderLoading, setFolderLoading] = useState(false)
  const [loadingModel, setLoadingModel] = useState<string | null>(null)

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
      const session = await sessionApi.create()
      setSessions((prev) => [session, ...prev])
      setActiveSession(session.id)
      setActiveSessionId(session.id)
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

  async function handleBrowseFolder() {
    if ((window as any).electronAPI?.openFolderDialog) {
      const path = await (window as any).electronAPI.openFolderDialog()
      if (path) {
        setModelFolder(path)
        setFolderLoading(true)
        try {
          const data = await modelApi.catalog(path)
          setFolderModels(data.models || [])
        } catch {}
        setFolderLoading(false)
      }
    } else {
      const path = prompt('Enter the path to your models folder:')
      if (path) {
        setModelFolder(path)
        setFolderLoading(true)
        try {
          const data = await modelApi.catalog(path)
          setFolderModels(data.models || [])
        } catch {}
        setFolderLoading(false)
      }
    }
  }

  async function handleLoadModelFromFolder(modelPath: string) {
    setLoadingModel(modelPath)
    try {
      if (modelInfo?.loaded) await modelApi.unload()
      const result = await modelApi.load(modelPath)
      setModelInfo(result)
      setLoadingModel(null)
    } catch {}
    setLoadingModel(null)
  }

  function formatDate(dateStr: string) {
    const d = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 60_000) return 'just now'
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
    return d.toLocaleDateString()
  }

  const leftTabs: { id: LeftTab; label: string; icon: typeof MessageSquare }[] = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'code', label: 'Code', icon: Code },
    { id: 'cowork', label: 'Cowork', icon: Users },
  ]

  return (
    <div className="w-64 h-full flex flex-col bg-surface border-r border-border">
      {/* Chat / Code / Cowork tabs */}
      <div className="flex border-b border-border" role="tablist">
        {leftTabs.map(tab => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setLeftTab(tab.id)}
              role="tab"
              aria-selected={leftTab === tab.id}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[11px] font-medium transition-colors ${
                leftTab === tab.id ? 'text-accent border-b-2 border-accent' : 'text-text-muted hover:text-text-sec'
              }`}
            >
              <Icon size={13} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Chat tab content */}
      {leftTab === 'chat' && (
        <>
      {/* Quick actions */}
      <div className="p-3 border-b border-border space-y-2">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2 px-3 py-2.5 bg-accent text-onAccent rounded-xl text-sm font-medium hover:bg-accent-hover transition-colors"
        >
          <Plus size={16} />
          New task
        </button>
        <button
          onClick={handleBrowseFolder}
          className="w-full flex items-center gap-2 px-3 py-2 bg-elevated border border-border rounded-xl text-sm text-text-sec hover:border-accent transition-colors"
        >
          <FolderOpen size={14} />
          Browse Models Folder
        </button>
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

      {/* Model folder browser */}
      {modelFolder && (
        <div className="px-3 py-2 border-b border-border">
          <div className="flex items-center gap-2 mb-2">
            <HardDrive size={12} className="text-accent flex-shrink-0" />
            <span className="text-[10px] text-text-muted truncate flex-1">{modelFolder.split(/[/\\]/).pop()}</span>
            <button onClick={() => { setModelFolder(''); setFolderModels([]) }} className="text-text-muted hover:text-text">
              <X size={10} />
            </button>
          </div>
          {folderLoading ? (
            <div className="flex items-center gap-2 text-xs text-text-muted py-2">
              <Loader2 size={12} className="animate-spin" /> Scanning...
            </div>
          ) : folderModels.length === 0 ? (
            <div className="text-xs text-text-muted py-2">No GGUF models found</div>
          ) : (
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {folderModels.map((model) => (
                <button
                  key={model.path}
                  onClick={() => handleLoadModelFromFolder(model.path)}
                  disabled={loadingModel === model.path}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-elevated transition-colors text-left"
                >
                  {loadingModel === model.path ? (
                    <Loader2 size={10} className="text-accent animate-spin flex-shrink-0" />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-text-muted flex-shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="text-[11px] text-text-sec truncate font-mono">{model.filename}</div>
                    <div className="flex items-center gap-1 text-[9px] text-text-muted">
                      {model.profile?.family && <span>{model.profile.family}</span>}
                      {model.profile?.quantization && <span>· {model.profile.quantization}</span>}
                      {model.size_gb && <span>· {model.size_gb} GB</span>}
                    </div>
                  </div>
                  <Zap size={10} className="text-accent flex-shrink-0" />
                </button>
              ))}
            </div>
          )}
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
                  onClick={async () => {
                    setActiveSession(session.id)
                    setActiveSessionId(session.id)
                    // Load session messages into chat
                    try {
                      const full = await sessionApi.get(session.id)
                      clearMessages()
                      if (full && full.messages) {
                        const chatStore = useChatStore.getState()
                        for (const msg of full.messages) {
                          if (msg.role === 'user' || msg.role === 'assistant') {
                            chatStore.addMessage({
                              id: `${msg.role}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
                              role: msg.role,
                              content: msg.content || '',
                              timestamp: Date.now(),
                            })
                          }
                        }
                      }
                    } catch {}
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
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(e) => {
                        e.stopPropagation()
                        setContextMenu(contextMenu === session.id ? null : session.id)
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.stopPropagation()
                          setContextMenu(contextMenu === session.id ? null : session.id)
                        }
                      }}
                      className="p-0.5 opacity-0 group-hover:opacity-100 text-text-muted hover:text-text transition-all cursor-pointer"
                    >
                      <MoreVertical size={12} />
                    </span>
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

      </>)}

      {/* Code tab — file explorer */}
      {leftTab === 'code' && (
        <div className="flex-1 overflow-hidden">
          <FileExplorer onFileSelect={() => {}} selectedFile={null} />
        </div>
      )}

      {/* Cowork tab — workspace overview */}
      {leftTab === 'cowork' && (
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          <div className="text-xs font-medium text-text-muted uppercase tracking-wider">Workspace</div>
          <div className="flex items-center gap-2 px-3 py-2 bg-elevated rounded-xl border border-border">
            <FolderOpen size={14} className="text-accent flex-shrink-0" />
            <span className="text-sm text-text truncate">{workspace || 'No workspace set'}</span>
          </div>
          <div className="text-xs font-medium text-text-muted uppercase tracking-wider mt-4">Recent Sessions</div>
          {sessions.slice(0, 5).map(s => (
            <div key={s.id} className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-sec">
              <MessageSquare size={11} className="text-text-muted" />
              <span className="truncate">{s.title || 'Untitled'}</span>
            </div>
          ))}
        </div>
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
