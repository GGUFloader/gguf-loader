import { useState, useEffect, useCallback } from 'react'
import { benchmarkApi } from '../../api/client'
import { BarChart3, TrendingUp, Clock, Zap, Trophy, RefreshCw } from 'lucide-react'

interface BenchmarkReport {
  id: string
  model_name: string
  timestamp: number
  overall_score: number
}

interface ReportDetail {
  model_name: string
  model_path: string
  summary: {
    avg_tps: number
    avg_ttft_ms: number
    avg_quality: number
    overall_score: number
    total_tokens: number
    total_time_ms: number
    category_scores: Record<string, number>
    prompt_count: number
  }
  results: Array<{
    prompt_id: string
    category: string
    tokens_per_second: number
    first_token_ms: number
    quality_score: number
    keyword_score: number
  }>
}

const BAR_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#f87171', '#a78bfa', '#fb923c', '#22d3ee']

function BarChart({ data, maxValue, label }: { data: { label: string; value: number; color: string }[]; maxValue: number; label: string }) {
  return (
    <div>
      <div className="text-[10px] text-text-muted uppercase tracking-wide mb-2">{label}</div>
      <div className="space-y-1.5">
        {data.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="text-[10px] text-text-sec w-20 truncate text-right">{item.label}</span>
            <div className="flex-1 bg-elevated rounded-full h-4 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500 flex items-center justify-end pr-1.5"
                style={{
                  width: `${maxValue > 0 ? (item.value / maxValue) * 100 : 0}%`,
                  backgroundColor: item.color,
                  minWidth: item.value > 0 ? '24px' : '0',
                }}
              >
                <span className="text-[8px] font-bold text-black drop-shadow-sm">{item.value.toFixed(1)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}



export function BenchmarkChartPanel() {
  const [reports, setReports] = useState<BenchmarkReport[]>([])
  const [selectedReports, setSelectedReports] = useState<string[]>([])
  const [reportDetails, setReportDetails] = useState<ReportDetail[]>([])
  const [prompts, setPrompts] = useState<any[]>([])
  const [history, setHistory] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState<'compare' | 'history' | 'prompts'>('compare')


  const loadReports = useCallback(async () => {
    try {
      const r = await benchmarkApi.reports()
      setReports(r)
    } catch { /* ok */ }
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const h = await benchmarkApi.history()
      setHistory(h)
    } catch { /* ok */ }
  }, [])

  const loadPrompts = useCallback(async () => {
    try {
      const p = await benchmarkApi.prompts()
      setPrompts(p)
    } catch { /* ok */ }
  }, [])

  useEffect(() => { loadReports(); loadHistory(); loadPrompts() }, [loadReports, loadHistory, loadPrompts])

  const toggleReport = async (id: string) => {
    const next = selectedReports.includes(id)
      ? selectedReports.filter(r => r !== id)
      : [...selectedReports, id].slice(0, 5) // max 5
    setSelectedReports(next)

    // Load details for newly selected
    if (next.length > selectedReports.length) {
      setLoading(true)
      try {
        const detail = await benchmarkApi.report(id)
        setReportDetails(prev => {
          const filtered = prev.filter(p => next.includes(reports.find(r => r.model_name === p.model_name)?.id || ''))
          return [...filtered, detail]
        })
      } catch { /* ok */ }
      setLoading(false)
    } else {
      setReportDetails(prev => prev.slice(0, next.length))
    }
  }

  const renderComparison = () => {
    if (reportDetails.length < 2) {
      return (
        <div className="flex-1 flex items-center justify-center text-text-muted text-xs">
          Select 2+ reports to compare
        </div>
      )
    }

    // Build chart data
    const tpsData = reportDetails.map((r, i) => ({
      label: r.model_name.slice(0, 12),
      value: r.summary.avg_tps,
      color: BAR_COLORS[i % BAR_COLORS.length],
    }))
    const ttftData = reportDetails.map((r, i) => ({
      label: r.model_name.slice(0, 12),
      value: r.summary.avg_ttft_ms,
      color: BAR_COLORS[i % BAR_COLORS.length],
    }))
    const qualityData = reportDetails.map((r, i) => ({
      label: r.model_name.slice(0, 12),
      value: r.summary.overall_score * 100,
      color: BAR_COLORS[i % BAR_COLORS.length],
    }))

    // Category scores for first model
    const catScores = reportDetails[0]?.summary.category_scores || {}
    const catData = Object.entries(catScores).map(([cat, score], i) => ({
      label: cat,
      value: (score as number) * 100,
      color: BAR_COLORS[i % BAR_COLORS.length],
    }))

    const maxTps = Math.max(...tpsData.map(d => d.value), 1)
    const maxTtft = Math.max(...ttftData.map(d => d.value), 1)
    const maxQuality = 100

    // Find winners
    const fastestModel = tpsData.reduce((a, b) => a.value > b.value ? a : b)
    const lowestLatency = ttftData.reduce((a, b) => a.value < b.value ? a : b)
    const bestQuality = qualityData.reduce((a, b) => a.value > b.value ? a : b)

    return (
      <div className="space-y-4 p-3">
        {/* Winner badges */}
        <div className="flex gap-2">
          <div className="flex-1 bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-2 text-center">
            <Trophy size={14} className="mx-auto text-emerald-400 mb-1" />
            <div className="text-[10px] text-emerald-400">Fastest</div>
            <div className="text-xs text-text font-medium">{fastestModel.label}</div>
            <div className="text-[10px] text-text-muted">{fastestModel.value.toFixed(1)} tok/s</div>
          </div>
          <div className="flex-1 bg-blue-500/10 border border-blue-500/30 rounded-lg p-2 text-center">
            <Clock size={14} className="mx-auto text-blue-400 mb-1" />
            <div className="text-[10px] text-blue-400">Lowest Latency</div>
            <div className="text-xs text-text font-medium">{lowestLatency.label}</div>
            <div className="text-[10px] text-text-muted">{lowestLatency.value.toFixed(0)}ms</div>
          </div>
          <div className="flex-1 bg-amber-500/10 border border-amber-500/30 rounded-lg p-2 text-center">
            <Zap size={14} className="mx-auto text-amber-400 mb-1" />
            <div className="text-[10px] text-amber-400">Best Quality</div>
            <div className="text-xs text-text font-medium">{bestQuality.label}</div>
            <div className="text-[10px] text-text-muted">{bestQuality.value.toFixed(1)}%</div>
          </div>
        </div>

        {/* Metric cards */}
        {reportDetails.map((r, i) => (
          <div key={i} className="bg-elevated rounded-lg border border-border p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-text font-medium">{r.model_name}</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: BAR_COLORS[i] + '33', color: BAR_COLORS[i] }}>
                Score: {(r.summary.overall_score * 100).toFixed(1)}%
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="text-center">
                <div className="text-lg font-bold text-text">{r.summary.avg_tps.toFixed(1)}</div>
                <div className="text-[9px] text-text-muted">tok/s</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-text">{r.summary.avg_ttft_ms.toFixed(0)}</div>
                <div className="text-[9px] text-text-muted">ms TTFT</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-text">{r.summary.total_tokens}</div>
                <div className="text-[9px] text-text-muted">tokens</div>
              </div>
            </div>
          </div>
        ))}

        {/* Charts */}
        <BarChart data={tpsData} maxValue={maxTps} label="⚡ Tokens per Second" />
        <BarChart data={ttftData} maxValue={maxTtft} label="⏱ First Token Latency (ms)" />
        <BarChart data={qualityData} maxValue={maxQuality} label="🏆 Quality Score (%)" />
        {catData.length > 0 && <BarChart data={catData} maxValue={100} label="📊 Category Scores" />}
      </div>
    )
  }

  const renderHistory = () => (
    <div className="p-3 space-y-2">
      {history.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-xs">
          <BarChart3 size={24} className="mx-auto mb-2 opacity-50" />
          No benchmark history yet
        </div>
      ) : (
        history.map((h, i) => (
          <div key={i} className="bg-elevated rounded-lg p-3 border border-border">
            <div className="flex items-center justify-between">
              <span className="text-sm text-text font-medium">{h.model_name}</span>
              <span className="text-[10px] text-text-muted">
                {new Date(h.timestamp * 1000).toLocaleDateString()}
              </span>
            </div>
            <div className="flex gap-4 mt-2 text-[10px] text-text-sec">
              <span>{h.avg_tps?.toFixed(1)} tok/s</span>
              <span>{h.avg_ttft?.toFixed(0)}ms TTFT</span>
              <span>{(h.overall_score * 100)?.toFixed(1)}% quality</span>
            </div>
            {/* Mini bar */}
            <div className="mt-2 h-1.5 bg-surface rounded-full overflow-hidden">
              <div
                className="h-full bg-accent rounded-full"
                style={{ width: `${(h.overall_score || 0) * 100}%` }}
              />
            </div>
          </div>
        ))
      )}
    </div>
  )

  const renderPrompts = () => (
    <div className="p-3 space-y-2">
      {prompts.map((p: any, i: number) => (
        <div key={i} className="bg-elevated rounded-lg p-3 border border-border">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/20 text-accent">{p.category}</span>
            <span className="text-xs text-text font-medium">{p.id}</span>
          </div>
          <p className="text-[11px] text-text-sec leading-relaxed">{p.prompt}</p>
          {p.expected_keywords?.length > 0 && (
            <div className="flex gap-1 mt-2 flex-wrap">
              {p.expected_keywords.map((kw: string, j: number) => (
                <span key={j} className="text-[9px] px-1.5 py-0.5 rounded bg-surface text-text-muted border border-border">
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )

  return (
    <div className="h-full flex flex-col">
      {/* Tabs */}
      <div className="flex border-b border-border">
        {([
          { id: 'compare' as const, label: 'Compare', icon: BarChart3 },
          { id: 'history' as const, label: 'History', icon: TrendingUp },
          { id: 'prompts' as const, label: 'Prompts', icon: Zap },
        ]).map(tab => (
          <button
            key={tab.id}
            onClick={() => setView(tab.id)}
            className={`flex-1 flex items-center justify-center gap-1 py-2 text-[11px] font-medium transition-colors ${
              view === tab.id ? 'text-accent border-b-2 border-accent' : 'text-text-muted hover:text-text-sec'
            }`}
          >
            <tab.icon size={12} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Report selector (compare view) */}
      {view === 'compare' && (
        <div className="p-2 border-b border-border">
          <div className="text-[10px] text-text-muted mb-1">Select reports to compare (max 5)</div>
          <div className="space-y-1 max-h-24 overflow-auto">
            {reports.length === 0 ? (
              <div className="text-[10px] text-text-muted py-2">No reports available</div>
            ) : (
              reports.map(r => (
                <label key={r.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedReports.includes(r.id)}
                    onChange={() => toggleReport(r.id)}
                    className="rounded border-border accent-accent"
                  />
                  <span className="text-xs text-text truncate">{r.model_name}</span>
                  <span className="text-[9px] text-text-muted ml-auto">
                    {(r.overall_score * 100).toFixed(1)}%
                  </span>
                </label>
              ))
            )}
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-text-muted text-xs">
            <RefreshCw size={16} className="animate-spin mr-2" />
            Loading...
          </div>
        ) : view === 'compare' ? (
          renderComparison()
        ) : view === 'history' ? (
          renderHistory()
        ) : (
          renderPrompts()
        )}
      </div>
    </div>
  )
}
