import { useState, useEffect, useCallback } from 'react'
import {
  ChevronRight,
  ChevronDown,
  FileText,
  Folder,
  FolderOpen,
  Search,
  RefreshCw,
  Loader2,
} from 'lucide-react'
import { filesApi } from '../../api/client'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import type { FileNode } from '../../api/types'

interface Props {
  onFileSelect?: (path: string) => void
  selectedFile?: string | null
}

const FILE_ICONS: Record<string, string> = {
  py: '🐍',
  js: '📜',
  ts: '📜',
  tsx: '⚛️',
  jsx: '⚛️',
  json: '📋',
  md: '📝',
  txt: '📄',
  yaml: '⚙️',
  yml: '⚙️',
  toml: '⚙️',
  css: '🎨',
  html: '🌐',
  sh: '🔧',
  bat: '🔧',
  go: '🐹',
  rs: '🦀',
  java: '☕',
  cpp: '⚡',
  c: '⚡',
  h: '📎',
  sql: '🗃️',
  xml: '📋',
  csv: '📊',
  png: '🖼️',
  jpg: '🖼️',
  gif: '🖼️',
  svg: '🎨',
  pdf: '📕',
  zip: '📦',
  tar: '📦',
  gz: '📦',
}

function getFileIcon(name: string, isDir: boolean): string {
  if (isDir) return ''
  const ext = name.split('.').pop()?.toLowerCase() || ''
  return FILE_ICONS[ext] || '📄'
}

function FileTreeNode({
  node,
  depth,
  selectedFile,
  onFileSelect,
}: {
  node: FileNode
  depth: number
  selectedFile?: string | null
  onFileSelect?: (path: string) => void
}) {
  const [expanded, setExpanded] = useState(depth < 1)

  const icon = getFileIcon(node.name, node.is_dir)
  const isSelected = selectedFile === node.path

  return (
    <div>
      <button
        onClick={() => {
          if (node.is_dir) {
            setExpanded(!expanded)
          } else {
            onFileSelect?.(node.path)
          }
        }}
        className={`w-full flex items-center gap-1.5 px-2 py-1 text-xs text-left transition-colors rounded ${
          isSelected
            ? 'bg-accent/15 text-accent'
            : 'text-text-sec hover:bg-elevated/60'
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {node.is_dir ? (
          <>
            {expanded ? (
              <ChevronDown size={12} className="flex-shrink-0 text-text-muted" />
            ) : (
              <ChevronRight size={12} className="flex-shrink-0 text-text-muted" />
            )}
            {expanded ? (
              <FolderOpen size={13} className="flex-shrink-0 text-yellow-400" />
            ) : (
              <Folder size={13} className="flex-shrink-0 text-yellow-400" />
            )}
          </>
        ) : (
          <>
            <span className="w-3" />
            {icon ? (
              <span className="text-xs">{icon}</span>
            ) : (
              <FileText size={13} className="flex-shrink-0 text-text-muted" />
            )}
          </>
        )}
        <span className="truncate">{node.name}</span>
      </button>

      {expanded && node.children && (
        <div>
          {node.children
            .sort((a, b) => {
              // Dirs first, then alphabetical
              if (a.is_dir && !b.is_dir) return -1
              if (!a.is_dir && b.is_dir) return 1
              return a.name.localeCompare(b.name)
            })
            .map((child) => (
              <FileTreeNode
                key={child.path}
                node={child}
                depth={depth + 1}
                selectedFile={selectedFile}
                onFileSelect={onFileSelect}
              />
            ))}
        </div>
      )}
    </div>
  )
}

export function FileExplorer({ onFileSelect, selectedFile }: Props) {
  const [tree, setTree] = useState<FileNode[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<FileNode[]>([])
  const workspace = useWorkspaceStore((s) => s.workspace)

  const loadTree = useCallback(async () => {
    setLoading(true)
    try {
      const data = await filesApi.tree(workspace || undefined)
      setTree(data)
    } catch {
      setTree([])
    }
    setLoading(false)
  }, [workspace])

  useEffect(() => {
    loadTree()
  }, [loadTree])

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      return
    }
    const timer = setTimeout(async () => {
      try {
        const results = await filesApi.search(searchQuery, workspace || undefined)
        setSearchResults(results)
      } catch {
        setSearchResults([])
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery, workspace])

  return (
    <div className="h-full flex flex-col">
      {/* Search bar */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-border">
        <Search size={12} className="text-text-muted flex-shrink-0" />
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search files..."
          className="flex-1 bg-transparent text-xs text-text placeholder-text-muted outline-none"
        />
        <button
          onClick={loadTree}
          className="p-0.5 text-text-muted hover:text-text rounded transition-colors"
          title="Refresh"
        >
          {loading ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
        </button>
      </div>

      {/* Search results or tree */}
      <div className="flex-1 overflow-y-auto py-1">
        {searchQuery && searchResults.length > 0 ? (
          <div>
            <div className="px-2 py-1 text-[10px] text-text-muted uppercase tracking-wider">
              Search Results ({searchResults.length})
            </div>
            {searchResults.map((file) => (
              <button
                key={file.path}
                onClick={() => onFileSelect?.(file.path)}
                className={`w-full flex items-center gap-2 px-2 py-1 text-xs text-left transition-colors rounded mx-1 ${
                  selectedFile === file.path
                    ? 'bg-accent/15 text-accent'
                    : 'text-text-sec hover:bg-elevated/60'
                }`}
              >
                <span className="text-xs">{getFileIcon(file.name, false) || '📄'}</span>
                <div className="min-w-0">
                  <div className="truncate font-medium">{file.name}</div>
                  <div className="truncate text-[10px] text-text-muted">{file.path}</div>
                </div>
              </button>
            ))}
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={16} className="animate-spin text-text-muted" />
          </div>
        ) : tree.length === 0 ? (
          <div className="text-center py-8 text-text-muted text-xs">
            No workspace loaded
          </div>
        ) : (
          tree.map((node) => (
            <FileTreeNode
              key={node.path}
              node={node}
              depth={0}
              selectedFile={selectedFile}
              onFileSelect={onFileSelect}
            />
          ))
        )}
      </div>
    </div>
  )
}
