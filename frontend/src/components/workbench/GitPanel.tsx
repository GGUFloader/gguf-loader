import { useState, useEffect, useCallback } from 'react'
import {
  GitBranch,
  RefreshCw,
  Loader2,
  Plus,
  FileEdit,
  FilePlus,
  FileX,
  ChevronRight,
  ChevronDown,
} from 'lucide-react'

interface GitFile {
  path: string
  status: 'modified' | 'added' | 'deleted' | 'renamed' | 'untracked'
}

interface GitStatus {
  branch: string
  files: GitFile[]
  ahead: number
  behind: number
  clean: boolean
}

export function GitPanel() {
  const [status, setStatus] = useState<GitStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [commitMsg, setCommitMsg] = useState('')
  const [committing, setCommitting] = useState(false)
  const [expandedDiff, setExpandedDiff] = useState<string | null>(null)
  const [diffContent, setDiffContent] = useState('')

  const loadStatus = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/files/git/status')
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      } else {
        setStatus(null)
      }
    } catch {
      setStatus(null)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  async function loadDiff(path: string) {
    if (expandedDiff === path) {
      setExpandedDiff(null)
      return
    }
    try {
      const res = await fetch(`/api/files/git/diff?path=${encodeURIComponent(path)}`)
      if (res.ok) {
        const data = await res.json()
        setDiffContent(data.diff || '')
        setExpandedDiff(path)
      }
    } catch {}
  }

  async function handleCommit() {
    if (!commitMsg.trim() || !status || status.files.length === 0) return
    setCommitting(true)
    try {
      await fetch('/api/files/git/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: commitMsg }),
      })
      setCommitMsg('')
      loadStatus()
    } catch {}
    setCommitting(false)
  }

  function getStatusIcon(s: string) {
    switch (s) {
      case 'modified':
        return <FileEdit size={12} className="text-yellow-400" />
      case 'added':
      case 'untracked':
        return <FilePlus size={12} className="text-green-400" />
      case 'deleted':
        return <FileX size={12} className="text-red-400" />
      default:
        return <FileEdit size={12} className="text-text-muted" />
    }
  }

  function getStatusLetter(s: string) {
    switch (s) {
      case 'modified': return 'M'
      case 'added': return 'A'
      case 'deleted': return 'D'
      case 'renamed': return 'R'
      case 'untracked': return '?'
      default: return ' '
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={16} className="animate-spin text-text-muted" />
      </div>
    )
  }

  if (!status) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-4">
        <GitBranch size={28} className="text-text-muted mb-3" />
        <p className="text-sm text-text-muted">Not a git repository</p>
        <button
          onClick={loadStatus}
          className="mt-2 text-xs text-accent hover:underline"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Branch info */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
        <GitBranch size={12} className="text-accent" />
        <span className="text-xs font-medium text-text">{status.branch}</span>
        {status.ahead > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 bg-accent/15 text-accent rounded">
            ↑{status.ahead}
          </span>
        )}
        {status.behind > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 bg-yellow-500/15 text-yellow-400 rounded">
            ↓{status.behind}
          </span>
        )}
        <button
          onClick={loadStatus}
          className="ml-auto p-0.5 text-text-muted hover:text-text rounded transition-colors"
          title="Refresh"
        >
          <RefreshCw size={11} />
        </button>
      </div>

      {/* Changed files */}
      <div className="flex-1 overflow-y-auto">
        {status.files.length === 0 ? (
          <div className="py-8 text-center text-xs text-text-muted">
            Working tree clean
          </div>
        ) : (
          <div>
            <div className="px-3 py-1.5 text-[10px] text-text-muted uppercase tracking-wider">
              Changes ({status.files.length})
            </div>
            {status.files.map((file) => (
              <div key={file.path}>
                <button
                  onClick={() => loadDiff(file.path)}
                  className="w-full flex items-center gap-1.5 px-3 py-1 text-xs text-left hover:bg-elevated/40 transition-colors"
                >
                  {expandedDiff === file.path ? (
                    <ChevronDown size={10} className="text-text-muted flex-shrink-0" />
                  ) : (
                    <ChevronRight size={10} className="text-text-muted flex-shrink-0" />
                  )}
                  {getStatusIcon(file.status)}
                  <span className={`flex-shrink-0 w-4 text-center font-mono text-[10px] ${
                    file.status === 'modified' ? 'text-yellow-400' :
                    file.status === 'added' ? 'text-green-400' :
                    file.status === 'deleted' ? 'text-red-400' :
                    'text-text-muted'
                  }`}>
                    {getStatusLetter(file.status)}
                  </span>
                  <span className="truncate text-text-sec">{file.path}</span>
                </button>

                {expandedDiff === file.path && diffContent && (
                  <div className="mx-3 mb-1 bg-bg rounded border border-border overflow-x-auto">
                    <pre className="text-[10px] font-mono p-2">
                      {diffContent.split('\n').map((line, i) => (
                        <div
                          key={i}
                          className={`${
                            line.startsWith('+') && !line.startsWith('+++')
                              ? 'text-green-400'
                              : line.startsWith('-') && !line.startsWith('---')
                              ? 'text-red-400'
                              : line.startsWith('@@')
                              ? 'text-accent'
                              : 'text-text-muted'
                          }`}
                        >
                          {line}
                        </div>
                      ))}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Commit input */}
      {status.files.length > 0 && (
        <div className="border-t border-border p-2 space-y-1.5">
          <div className="flex gap-1.5">
            <input
              value={commitMsg}
              onChange={(e) => setCommitMsg(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCommit()}
              placeholder="Commit message..."
              className="flex-1 bg-elevated border border-border rounded px-2 py-1.5 text-xs text-text placeholder-text-muted outline-none focus:border-accent"
              disabled={committing}
            />
            <button
              onClick={handleCommit}
              disabled={!commitMsg.trim() || committing}
              className="px-3 py-1.5 bg-accent text-onAccent rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors"
            >
              {committing ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
