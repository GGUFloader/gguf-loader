import { useState } from 'react'
import { GitCompare, Split, List, Plus, Minus, RefreshCw } from 'lucide-react'
import { diffApi } from '../../api/client'

interface DiffLine {
  old_line: number | null
  new_line: number | null
  old_text: string
  new_text: string
  type: 'equal' | 'replace' | 'delete' | 'insert'
}

interface DiffResult {
  filename: string
  lines: DiffLine[]
  stats: { additions: number; deletions: number }
}

interface HunkLine {
  type: 'add' | 'delete' | 'context' | 'info'
  content: string
}

interface Hunk {
  old_start: number
  new_start: number
  header: string
  lines: HunkLine[]
}

interface UnifiedDiff {
  filename: string
  hunks: Hunk[]
  stats: { additions: number; deletions: number; total_changes: number }
  raw: string
}

export function DiffViewerPanel() {
  const [oldText, setOldText] = useState('')
  const [newText, setNewText] = useState('')
  const [filename, setFilename] = useState('')
  const [mode, setMode] = useState<'side-by-side' | 'unified'>('side-by-side')
  const [result, setResult] = useState<DiffResult | UnifiedDiff | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleCompute() {
    if (!oldText && !newText) return
    setLoading(true)
    setError(null)
    try {
      if (mode === 'side-by-side') {
        const data = await diffApi.sideBySide(oldText, newText, filename)
        setResult(data)
      } else {
        const data = await diffApi.compute(oldText, newText, filename)
        setResult(data)
      }
    } catch (e: any) {
      setError(e.message || 'Failed to compute diff')
    }
    setLoading(false)
  }

  function loadExample() {
    setOldText(`function greet(name) {\n  console.log("Hello, " + name);\n  return true;\n}\n\nfunction add(a, b) {\n  return a - b;\n}`)
    setNewText(`function greet(name, greeting = "Hello") {\n  const msg = \`\${greeting}, \${name}!\`;\n  console.log(msg);\n  return msg;\n}\n\nfunction add(a, b) {\n  return a + b;\n}\n\nfunction multiply(a, b) {\n  return a * b;\n}`)
    setFilename('utils.js')
  }

  const isSideBySide = result && 'lines' in result
  const isUnified = result && 'hunks' in result
  const stats = result?.stats

  return (
    <div className="h-full flex flex-col p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <GitCompare size={14} className="text-accent" />
          Diff Viewer
        </h3>
      </div>

      {/* Inputs */}
      {!result && (
        <div className="space-y-2">
          <input placeholder="Filename (optional)" value={filename} onChange={e => setFilename(e.target.value)}
            className="w-full bg-elevated border border-border rounded-lg px-3 py-1.5 text-[11px] text-text outline-none focus:border-accent" />

          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="text-[9px] text-text-muted uppercase mb-1">Original</div>
              <textarea placeholder="Original text..." value={oldText} onChange={e => setOldText(e.target.value)}
                className="w-full h-32 bg-elevated border border-border rounded-lg px-3 py-2 text-[10px] text-text font-mono outline-none focus:border-accent resize-none" />
            </div>
            <div>
              <div className="text-[9px] text-text-muted uppercase mb-1">Modified</div>
              <textarea placeholder="Modified text..." value={newText} onChange={e => setNewText(e.target.value)}
                className="w-full h-32 bg-elevated border border-border rounded-lg px-3 py-2 text-[10px] text-text font-mono outline-none focus:border-accent resize-none" />
            </div>
          </div>

          <div className="flex gap-2">
            <button onClick={loadExample} className="px-3 py-1.5 bg-elevated border border-border rounded-lg text-[10px] text-text-sec hover:border-accent/30 transition-colors">
              Load Example
            </button>
            <div className="flex-1 flex gap-1 bg-elevated rounded-lg p-0.5">
              <button onClick={() => setMode('side-by-side')}
                className={`flex-1 flex items-center justify-center gap-1 text-[10px] py-1 rounded-md transition-colors ${mode === 'side-by-side' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
                <Split size={10} /> Side by Side
              </button>
              <button onClick={() => setMode('unified')}
                className={`flex-1 flex items-center justify-center gap-1 text-[10px] py-1 rounded-md transition-colors ${mode === 'unified' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
                <List size={10} /> Unified
              </button>
            </div>
            <button onClick={handleCompute} disabled={loading || (!oldText && !newText)}
              className="flex items-center justify-center gap-1 px-4 py-1.5 bg-accent text-onAccent rounded-lg text-[11px] font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">
              <GitCompare size={11} /> {loading ? 'Computing...' : 'Diff'}
            </button>
          </div>
        </div>
      )}

      {error && <div className="text-[10px] text-red-400 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>}

      {/* Diff result */}
      {result && (
        <div className="space-y-2">
          {/* Header */}
          <div className="flex items-center justify-between bg-elevated border border-border rounded-lg px-3 py-2">
            <div className="flex items-center gap-2">
              {filename && <span className="text-[10px] text-text font-mono">{filename}</span>}
              <span className="text-[9px] text-text-muted">{mode}</span>
            </div>
            <div className="flex items-center gap-3 text-[9px]">
              <span className="text-green-400 flex items-center gap-0.5"><Plus size={9} /> {stats?.additions || 0}</span>
              <span className="text-red-400 flex items-center gap-0.5"><Minus size={9} /> {stats?.deletions || 0}</span>
            </div>
          </div>

          {/* Side-by-side view */}
          {isSideBySide && (
            <div className="bg-bg border border-border rounded-lg overflow-hidden text-[10px] font-mono">
              {(result as DiffResult).lines.map((line, i) => (
                <div key={i} className={`flex ${line.type === 'replace' ? 'bg-amber-500/5' : line.type === 'insert' ? 'bg-green-500/5' : line.type === 'delete' ? 'bg-red-500/5' : ''}`}>
                  <span className="w-10 text-right pr-1 text-text-muted/40 select-none flex-shrink-0">{line.old_line || ''}</span>
                  <span className="w-10 text-right pr-1 text-text-muted/40 select-none flex-shrink-0">{line.new_line || ''}</span>
                  <span className="w-4 text-center select-none flex-shrink-0">
                    {line.type === 'insert' && <span className="text-green-400">+</span>}
                    {line.type === 'delete' && <span className="text-red-400">-</span>}
                    {line.type === 'replace' && <span className="text-amber-400">~</span>}
                  </span>
                  <span className="w-1/2 px-2 py-0.5 border-r border-border/30 whitespace-pre-wrap break-all">{line.old_text}</span>
                  <span className="w-1/2 px-2 py-0.5 whitespace-pre-wrap break-all">{line.new_text}</span>
                </div>
              ))}
            </div>
          )}

          {/* Unified view */}
          {isUnified && (
            <div className="bg-bg border border-border rounded-lg overflow-hidden text-[10px] font-mono">
              {(result as UnifiedDiff).hunks.map((hunk, hi) => (
                <div key={hi}>
                  <div className="px-3 py-1 bg-elevated/50 text-[9px] text-accent border-b border-border/50">
                    @@ -{hunk.old_start} +{hunk.new_start} @@ {hunk.header}
                  </div>
                  {hunk.lines.map((line, li) => (
                    <div key={li} className={`px-3 py-0.5 whitespace-pre-wrap break-all ${
                      line.type === 'add' ? 'bg-green-500/10 text-green-400' :
                      line.type === 'delete' ? 'bg-red-500/10 text-red-400' : 'text-text-sec'
                    }`}>
                      <span className="select-none text-text-muted/40">{line.type === 'add' ? '+' : line.type === 'delete' ? '-' : ' '}</span>
                      {' '}{line.content}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* Back button */}
          <button onClick={() => setResult(null)}
            className="w-full flex items-center justify-center gap-1 px-3 py-1.5 bg-elevated border border-border rounded-lg text-[10px] text-text-sec hover:border-accent/30 transition-colors">
            <RefreshCw size={10} /> New Diff
          </button>
        </div>
      )}
    </div>
  )
}
