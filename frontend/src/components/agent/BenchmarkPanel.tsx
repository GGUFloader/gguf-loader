import { useState, useEffect } from 'react'
import { Zap, RefreshCw, BarChart3 } from 'lucide-react'

interface BenchmarkResult {
  prompt_id: string
  category: string
  tokens_generated: number
  generation_time_ms: number
  first_token_ms: number
  tokens_per_second: number
  keyword_score: number
  quality_score: number
}

interface BenchmarkReport {
  model_name: string
  model_path: string
  timestamp: number
  results: BenchmarkResult[]
  summary: Record<string, any>
}

const CATEGORY_COLORS: Record<string, string> = {
  reasoning: 'text-blue-400 bg-blue-500/10',
  coding: 'text-amber-400 bg-amber-500/10',
  writing: 'text-green-400 bg-green-500/10',
  math: 'text-purple-400 bg-purple-500/10',
  general: 'text-text-muted bg-elevated',
}

export function BenchmarkPanel() {
  const [history, setHistory] = useState<any[]>([])
  const [reports, setReports] = useState<any[]>([])
  const [selectedReport, setSelectedReport] = useState<BenchmarkReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'history' | 'reports'>('history')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [h, r] = await Promise.all([
        fetch('/api/benchmark/history').then(r => r.json()),
        fetch('/api/benchmark/reports').then(r => r.json()),
      ])
      setHistory(h)
      setReports(r)
    } catch {}
    setLoading(false)
  }

  async function loadReport(id: string) {
    try {
      const data = await fetch(`/api/benchmark/reports/${id}`).then(r => r.json())
      setSelectedReport(data)
    } catch {}
  }

  function formatTime(ts: number) {
    if (!ts) return ''
    return new Date(ts * 1000).toLocaleDateString()
  }

  return (
    <div className="h-full flex flex-col p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Zap size={14} className="text-accent" />
          Benchmark
        </h3>
        <button onClick={loadData} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-elevated rounded-lg p-0.5">
        <button onClick={() => { setActiveTab('history'); setSelectedReport(null) }}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'history' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
          History ({history.length})
        </button>
        <button onClick={() => { setActiveTab('reports'); setSelectedReport(null) }}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'reports' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
          Reports ({reports.length})
        </button>
      </div>

      {loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Loading benchmark data...</div>
      ) : selectedReport ? (
        /* Report detail */
        <div className="space-y-3">
          <button onClick={() => setSelectedReport(null)} className="text-[11px] text-accent hover:text-accent-hover">← Back</button>

          <div className="bg-elevated border border-border rounded-lg px-3 py-2">
            <div className="text-xs font-medium text-text">{selectedReport.model_name}</div>
            <div className="text-[9px] text-text-muted">{formatTime(selectedReport.timestamp)}</div>
          </div>

          {/* Summary */}
          {selectedReport.summary && (
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-elevated border border-border rounded-lg px-2 py-1.5 text-center">
                <div className="text-lg font-semibold text-text">{selectedReport.summary.avg_tps || 0}</div>
                <div className="text-[9px] text-text-muted">Avg tok/s</div>
              </div>
              <div className="bg-elevated border border-border rounded-lg px-2 py-1.5 text-center">
                <div className="text-lg font-semibold text-text">{selectedReport.summary.avg_ttft_ms || 0}ms</div>
                <div className="text-[9px] text-text-muted">Avg TTFT</div>
              </div>
              <div className="bg-elevated border border-border rounded-lg px-2 py-1.5 text-center">
                <div className="text-lg font-semibold text-accent">{(selectedReport.summary.overall_score || 0).toFixed(2)}</div>
                <div className="text-[9px] text-text-muted">Overall Score</div>
              </div>
              <div className="bg-elevated border border-border rounded-lg px-2 py-1.5 text-center">
                <div className="text-lg font-semibold text-text">{(selectedReport as any).result_count || 0}</div>
                <div className="text-[9px] text-text-muted">Prompts</div>
              </div>
            </div>
          )}

          {/* Category scores */}
          {selectedReport.summary?.category_scores && (
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] text-text-muted uppercase mb-2">Category Scores</div>
              {Object.entries(selectedReport.summary.category_scores).map(([cat, score]) => (
                <div key={cat} className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] text-text-sec w-20">{cat}</span>
                  <div className="flex-1 h-2 bg-bg rounded-full overflow-hidden">
                    <div className="h-full bg-accent rounded-full" style={{ width: `${(score as number) * 100}%` }} />
                  </div>
                  <span className="text-[9px] text-text-muted w-8 text-right">{((score as number) * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          )}

          {/* Individual results */}
          <div className="space-y-1">
            {selectedReport.results?.map((r: BenchmarkResult, i: number) => (
              <div key={i} className="bg-elevated border border-border rounded-lg px-3 py-1.5">
                <div className="flex items-center gap-2">
                  <span className={`text-[8px] px-1.5 py-0.5 rounded ${CATEGORY_COLORS[r.category] || CATEGORY_COLORS.general}`}>
                    {r.category}
                  </span>
                  <span className="text-[10px] text-text flex-1">{r.prompt_id}</span>
                  <span className="text-[9px] text-text-muted">{r.tokens_per_second.toFixed(1)} tok/s</span>
                  <span className="text-[9px] text-accent">{(r.quality_score * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : activeTab === 'history' ? (
        <div className="space-y-1.5">
          {history.length === 0 ? (
            <div className="text-center py-8 text-text-muted text-xs">
              <Zap size={24} className="mx-auto mb-2 opacity-30" />
              <p>No benchmark history</p>
              <p className="mt-1 text-text-muted/50">Run a benchmark from the agent to see results</p>
            </div>
          ) : (
            history.map((h, i) => (
              <div key={i} className="bg-elevated border border-border rounded-lg px-3 py-2">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-[11px] text-text font-medium">{h.model_name}</div>
                    <div className="text-[9px] text-text-muted">{formatTime(h.timestamp)}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-accent">{h.avg_tps} tok/s</div>
                    <div className="text-[9px] text-text-muted">score: {(h.overall_score || 0).toFixed(2)}</div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="space-y-1.5">
          {reports.length === 0 ? (
            <div className="text-center py-8 text-text-muted text-xs">
              <BarChart3 size={24} className="mx-auto mb-2 opacity-30" />
              <p>No reports yet</p>
            </div>
          ) : (
            reports.map(r => (
              <button key={r.id} onClick={() => loadReport(r.id)}
                className="w-full text-left bg-elevated border border-border rounded-lg px-3 py-2 hover:border-accent/30 transition-colors">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-[11px] text-text font-medium">{r.model_name}</div>
                    <div className="text-[9px] text-text-muted">{formatTime(r.timestamp)}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-accent">{(r.overall_score || 0).toFixed(2)}</div>
                    <div className="text-[9px] text-text-muted">score</div>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
