import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'
import { filesApi } from '../../api/client'
import type { FileNode } from '../../api/types'

interface Props {
  query: string
  onSelect: (filePath: string) => void
  onClose: () => void
}

export function FileMentionPopup({ query, onSelect, onClose }: Props) {
  const [files, setFiles] = useState<FileNode[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadFiles()
  }, [])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  async function loadFiles() {
    try {
      const tree = await filesApi.tree()
      const flat = flattenTree(tree)
      setFiles(flat)
    } catch {}
    setLoading(false)
  }

  function flattenTree(nodes: FileNode[]): FileNode[] {
    const result: FileNode[] = []
    for (const node of nodes) {
      if (!node.is_dir) result.push(node)
      if (node.children) result.push(...flattenTree(node.children))
    }
    return result
  }

  const filtered = files.filter((f) =>
    f.name.toLowerCase().includes(query.toLowerCase()) ||
    f.path.toLowerCase().includes(query.toLowerCase())
  ).slice(0, 10)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (filtered[selectedIndex]) {
          onSelect(filtered[selectedIndex].path)
        }
      } else if (e.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [filtered, selectedIndex, onSelect, onClose])

  if (loading) {
    return (
      <div className="absolute bottom-full left-0 mb-2 w-80 bg-elevated border border-border rounded-lg shadow-lg p-3">
        <div className="text-sm text-text-muted">Loading files...</div>
      </div>
    )
  }

  if (filtered.length === 0) {
    return (
      <div className="absolute bottom-full left-0 mb-2 w-80 bg-elevated border border-border rounded-lg shadow-lg p-3">
        <div className="text-sm text-text-muted">No matching files</div>
      </div>
    )
  }

  return (
    <div className="absolute bottom-full left-0 mb-2 w-80 bg-elevated border border-border rounded-lg shadow-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-border text-xs text-text-muted">
        Select a file to attach
      </div>
      <div className="max-h-60 overflow-y-auto">
        {filtered.map((file, i) => (
          <button
            key={file.path}
            onClick={() => onSelect(file.path)}
            className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
              i === selectedIndex
                ? 'bg-accent/20 text-accent'
                : 'text-text hover:bg-elevated/50'
            }`}
          >
            <FileText size={14} className="flex-shrink-0 text-text-muted" />
            <div className="min-w-0">
              <div className="truncate font-medium">{file.name}</div>
              <div className="truncate text-xs text-text-muted">{file.path}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
