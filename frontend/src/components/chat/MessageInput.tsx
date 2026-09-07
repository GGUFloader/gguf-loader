import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { Send, Square, Plus, ChevronDown, Loader2, HardDrive, Zap, FolderOpen, Download, CheckCircle2 } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { modelApi } from '../../api/client'
import { useModelStore } from '../../stores/modelStore'
import { useDownloadStore } from '../../stores/downloadStore'
import { FileMentionPopup } from './FileMentionPopup'
import { ChatAutocomplete, detectTrigger } from './ChatAutocomplete'

interface FolderModel {
  path: string
  filename: string
  size_gb?: number
  profile?: {
    family?: string
    quantization?: string
    architecture?: string
  }
}

export function MessageInput() {
  const [input, setInput] = useState('')
  const [showMentions, setShowMentions] = useState(false)
  const [mentionQuery, setMentionQuery] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { isStreaming, sendMessage, stopStreaming } = useChatStore()

  const [showAutocomplete, setShowAutocomplete] = useState(false)
  const [acTrigger, setAcTrigger] = useState('')
  const [acQuery, setAcQuery] = useState('')

  // Model folder state
  const [modelFolder, setModelFolder] = useState('')
  const [folderModels, setFolderModels] = useState<FolderModel[]>([])
  const [folderLoading, setFolderLoading] = useState(false)
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [showModelPicker, setShowModelPicker] = useState(false)
  const [loadingModel, setLoadingModel] = useState<string | null>(null)
  // Download lifecycle lives in the shared store so the header chip can
  // render progress even while this picker is closed.
  const dl = useDownloadStore((s) => s.dl)
  const startDownload = useDownloadStore((s) => s.startDownload)
  // Whether the pinned model is already detected + loaded by the backend.
  const modelInfo = useModelStore((s) => s.info)

  // Workspace state (shared with LeftPanel)
  const workspace = useWorkspaceStore((s) => s.workspace)
  const setWorkspace = useWorkspaceStore((s) => s.setWorkspace)
  const [showWorkspacePicker, setShowWorkspacePicker] = useState(false)

  // Load model folder from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('ggufloader_model_folder')
      if (saved) {
        setModelFolder(saved)
        loadModelsFromFolder(saved)
      }
    } catch {}
  }, [])

  // When the shared download finishes, re-point the picker at the models
  // folder so the freshly downloaded file shows up in the list.
  const dlDoneHandled = useRef(false)
  useEffect(() => {
    if (dl?.status === 'done') {
      if (dlDoneHandled.current) return
      dlDoneHandled.current = true
      const dir = String(dl.path || '').replace(/(\\|\/)[^\\/]+\.gguf$/i, '')
      if (dir) {
        setModelFolder(dir)
        localStorage.setItem('ggufloader_model_folder', dir)
        loadModelsFromFolder(dir)
      }
      setSelectedModel(dl.path || '')
    } else {
      dlDoneHandled.current = false
    }
  }, [dl])

  async function loadModelsFromFolder(folder: string) {
    if (!folder) return
    setFolderLoading(true)
    try {
      const data = await modelApi.catalog(folder)
      setFolderModels(data.models || [])
    } catch {}
    setFolderLoading(false)
  }

  async function handleBrowseFolder() {
    if ((window as any).electronAPI?.openFolderDialog) {
      const path = await (window as any).electronAPI.openFolderDialog()
      if (path) {
        setModelFolder(path)
        localStorage.setItem('ggufloader_model_folder', path)
        loadModelsFromFolder(path)
      }
    } else {
      const path = prompt('Enter the path to your models folder:')
      if (path) {
        setModelFolder(path)
        localStorage.setItem('ggufloader_model_folder', path)
        loadModelsFromFolder(path)
      }
    }
    setShowModelPicker(false)
  }

  async function handleLoadModel(model: FolderModel) {
    setLoadingModel(model.path)
    setSelectedModel(model.path)
    try {
      await useModelStore.getState().loadModel(model.path)
    } catch {}
    setLoadingModel(null)
    setShowModelPicker(false)
  }

  // Download the pinned Gemma 4 12B Q4_K_M when no model is present. The
  // store owns the background poll so progress keeps updating in the
  // header chip even with the picker closed.
  async function handleDownloadPinned() {
    await startDownload()
  }

  function handleWorkspaceChange(newWorkspace: string) {
    if (newWorkspace === workspace) {
      setShowWorkspacePicker(false)
      return
    }
    setWorkspace(newWorkspace)
    // Clear chat for fresh start
    useChatStore.getState().clearMessages()
    setShowWorkspacePicker(false)
  }

  async function handleBrowseWorkspace() {
    if ((window as any).electronAPI?.openFolderDialog) {
      const path = await (window as any).electronAPI.openFolderDialog()
      if (path) handleWorkspaceChange(path)
    } else {
      const path = prompt('Enter workspace folder path:')
      if (path) handleWorkspaceChange(path)
    }
    setShowWorkspacePicker(false)
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value
    setInput(val)

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
    const triggerIdx = textBeforeCursor.search(/\/\w*$/)
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
    if (showMentions || showAutocomplete) return
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Get display name for current model
  const currentModelDisplay = selectedModel
    ? folderModels.find(m => m.path === selectedModel)?.filename || 'Local Model'
    : 'Local Model'

  // Get short workspace name for display
  const workspaceShort = workspace.split(/[/\\]/).pop() || workspace

  return (
    <div className="px-4 pb-4 pt-2 relative">
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

      {/* Input container */}
      <div className="bg-elevated border border-border rounded-2xl px-4 py-3 flex items-end gap-2">
        {/* Plus/attach button */}
        <button
          className="p-1 text-text-muted hover:text-text transition-colors mb-0.5"
          title="Attach file"
        >
          <Plus size={18} />
        </button>

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Reply..."
          rows={1}
          data-chat-input
          aria-label="Chat message input"
          className="flex-1 bg-transparent text-text placeholder-text-muted outline-none resize-none text-sm"
          style={{ minHeight: '24px', maxHeight: '120px' }}
        />

        {/* Workspace selector */}
        <div className="relative mb-0.5">
          <button
            onClick={() => setShowWorkspacePicker(!showWorkspacePicker)}
            className="flex items-center gap-1 px-2 py-1 text-[11px] text-text-muted hover:text-text-sec rounded-lg hover:bg-bg/50 transition-colors"
            title={`Workspace: ${workspace}`}
          >
            <FolderOpen size={10} />
            <span>{workspaceShort}</span>
            <ChevronDown size={10} />
          </button>

          {showWorkspacePicker && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowWorkspacePicker(false)} />
              <div className="absolute bottom-full right-0 mb-1 w-64 bg-elevated border border-border rounded-xl shadow-xl z-50 overflow-hidden">
                <div className="px-3 py-2 border-b border-border bg-bg/50">
                  <div className="text-[10px] text-text-muted font-medium">Workspace</div>
                  <div className="text-[10px] text-text truncate mt-0.5" title={workspace}>{workspace}</div>
                </div>

                <button
                  onClick={handleBrowseWorkspace}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-bg/50 transition-colors text-xs text-text"
                >
                  <FolderOpen size={12} className="text-accent" />
                  <span>Browse for workspace...</span>
                </button>

                <button
                  onClick={() => handleWorkspaceChange('.')}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-bg/50 transition-colors text-xs ${
                    workspace === '.' ? 'text-accent' : 'text-text'
                  }`}
                >
                  <HardDrive size={12} />
                  <span>App directory (default)</span>
                </button>
              </div>
            </>
          )}
        </div>

        {/* Model selector */}
        <div className="relative mb-0.5">
          <button
            onClick={() => setShowModelPicker(!showModelPicker)}
            className="flex items-center gap-1 px-2 py-1 text-[11px] text-text-muted hover:text-text-sec rounded-lg hover:bg-bg/50 transition-colors"
          >
            <span>{currentModelDisplay}</span>
            <ChevronDown size={10} />
          </button>

          {showModelPicker && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowModelPicker(false)} />
              <div className="absolute bottom-full right-0 mb-1 w-72 bg-elevated border border-border rounded-xl shadow-xl z-50 overflow-hidden max-h-80 overflow-y-auto">
                {/* Folder header */}
                <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-bg/50">
                  <div className="flex items-center gap-2 min-w-0">
                    <HardDrive size={12} className="text-accent flex-shrink-0" />
                    <span className="text-[10px] text-text-muted truncate">
                      {modelFolder ? modelFolder.split(/[/\\]/).pop() : 'No folder selected'}
                    </span>
                  </div>
                  <button
                    onClick={handleBrowseFolder}
                    className="text-[10px] text-accent hover:text-accent-hover flex-shrink-0"
                  >
                    Browse
                  </button>
                </div>

                {/* Loading state */}
                {folderLoading && (
                  <div className="flex items-center gap-2 px-3 py-3 text-xs text-text-muted">
                    <Loader2 size={12} className="animate-spin" />
                    Scanning folder...
                  </div>
                )}

                {/* Model list */}
                {folderModels.map((model) => (
                  <button
                    key={model.path}
                    onClick={() => handleLoadModel(model)}
                    disabled={loadingModel === model.path}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-bg/50 transition-colors ${
                      selectedModel === model.path ? 'bg-accent/10' : ''
                    } ${loadingModel === model.path ? 'opacity-60' : ''}`}
                  >
                    {loadingModel === model.path ? (
                      <Loader2 size={12} className="text-accent animate-spin flex-shrink-0" />
                    ) : (
                      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        selectedModel === model.path ? 'bg-accent' : 'bg-text-muted'
                      }`} />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-text truncate">{model.filename}</div>
                      <div className="flex items-center gap-1 text-[10px] text-text-muted">
                        {model.profile?.family && <span>{model.profile.family}</span>}
                        {model.profile?.quantization && <span>· {model.profile.quantization}</span>}
                        {model.size_gb && <span>· {model.size_gb} GB</span>}
                      </div>
                    </div>
                    <Zap size={10} className="text-accent flex-shrink-0 opacity-0 group-hover:opacity-100" />
                  </button>
                ))}

                {/* No model present → offer the pinned download (unless the
                    pinned model is already detected + loaded - then no
                    download is needed) */}
                {!folderLoading && folderModels.length === 0 && (
                  modelInfo.loaded ? (
                    <div className="border-t border-border px-3 py-3">
                      <div className="flex items-center gap-1.5 text-[11px] text-green-400">
                        <CheckCircle2 size={11} className="flex-shrink-0" />
                        <span className="truncate">
                          Model ready: {modelInfo.filename || 'Gemma 4 12B Q4_K_M'}
                        </span>
                      </div>
                      <p className="mt-1 text-[10px] text-text-muted leading-snug">
                        This folder is empty, but the pinned Gemma 4 12B Q4_K_M is
                        already loaded — no download needed.
                      </p>
                    </div>
                  ) : (
                  <div className="border-t border-border px-3 py-3 space-y-2">
                    <p className="text-[11px] text-text-muted leading-snug">
                      {modelFolder
                        ? 'No GGUF models found in this folder.'
                        : 'No model folder selected.'}{' '}
                      Download the pinned Gemma 4 12B Q4_K_M instead:
                    </p>
                    {(!dl || dl.status === 'idle' || dl.status === 'disabled') && (
                      <button onClick={handleDownloadPinned}
                        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-accent/10 border border-accent/25 rounded-lg text-[11px] font-medium text-accent hover:bg-accent/20 transition-colors">
                        <Download size={11} /> Download Gemma 4 12B Q4_K_M (~8 GB)
                      </button>
                    )}
                    {dl?.status === 'downloading' && (
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-1.5 text-[10px] text-text-muted">
                          <Loader2 size={10} className="animate-spin" />
                          <span>Downloading...</span>
                          <span className="ml-auto font-mono text-text-sec">{Math.round(dl.progress * 100)}%</span>
                        </div>
                        <div className="h-1.5 bg-elevated border border-border rounded-full overflow-hidden">
                          <div className="h-full bg-accent transition-all duration-500"
                            style={{ width: `${Math.min(100, Math.max(0, Math.round(dl.progress * 100)))}%` }} />
                        </div>
                      </div>
                    )}
                    {dl?.status === 'done' && (
                      <div className="flex items-center gap-1.5 text-[11px] text-green-400">
                        <CheckCircle2 size={11} /> Downloaded — loading model...
                      </div>
                    )}
                    {dl?.status === 'error' && (
                      <div className="space-y-1.5">
                        <p className="text-[10px] text-red-400 leading-snug">{dl.message || 'Download failed'}</p>
                        <button onClick={handleDownloadPinned}
                          className="w-full px-3 py-1.5 bg-elevated border border-border rounded-lg text-[11px] text-text-sec hover:border-accent transition-colors">
                          Retry download
                        </button>
                      </div>
                    )}
                  </div>
                  )
                )}
              </div>
            </>
          )}
        </div>

        {/* Send/Stop button */}
        <button
          onClick={isStreaming ? stopStreaming : handleSend}
          disabled={!input.trim() && !isStreaming}
          className={`p-2 rounded-xl transition-colors ${
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
    </div>
  )
}
