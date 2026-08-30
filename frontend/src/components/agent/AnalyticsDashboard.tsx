import { useState, useEffect } from 'react'
import { BarChart3, RefreshCw, TrendingUp, Zap, DollarSign, MessageSquare } from 'lucide-react'
import { agentApi, sessionApi } from '../../api/client'

interface AnalyticsData {
  sessions: { total: number; recent: number }
  tokens: { input: number; output: number; total: number }
  costs: { electricity_usd: number; api_comparison_usd: number; savings_usd: number }
  throughput: { avg_tps: number; peak_tps: number }
  tools: { total_calls: number; success_rate: number }
  timeline: { date: string; sessions: number; tokens: number }[]
}

export function AnalyticsDashboard() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState<'7d' | '30d' | 'all'>('7d')

  useEffect(() => { loadAnalytics() }, [period])

  async function loadAnalytics() {
    setLoading(true)
    try {
      const [health, sessions] = await Promise.all([
        agentApi.health(),
        sessionApi.list(),
      ])

      const cost = health.cost || {}
      const healthData = health.health || {}
      const gauges = healthData.gauges || {}
      const counters = healthData.counters || {}

      const analytics: AnalyticsData = {
        sessions: {
          total: sessions.length || 0,
          recent: sessions.filter((s: any) => {
            const d = new Date(s.updated || s.created)
            const diff = Date.now() - d.getTime()
            const days = period === '7d' ? 7 : period === '30d' ? 30 : 9999
            return diff < days * 86_400_000
          }).length || 0,
        },
        tokens: {
          input: cost.input_tokens || 0,
          output: cost.output_tokens || 0,
          total: cost.total_tokens || 0,
        },
        costs: {
          electricity_usd: cost.electricity_cost_usd || 0,
          api_comparison_usd: cost.api_cost_comparison?.total || 0,
          savings_usd: cost.savings_vs_api || 0,
        },
        throughput: {
          avg_tps: cost.throughput?.tokens_per_second || 0,
          peak_tps: gauges.peak_tps || 0,
        },
        tools: {
          total_calls: counters.tool_calls || 0,
          success_rate: counters.tool_calls > 0
            ? (counters.tool_successes || 0) / counters.tool_calls
            : 1,
        },
        timeline: generateTimeline(sessions, period),
      }

      setData(analytics)
    } catch {}
    setLoading(false)
  }

  function formatNumber(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
    return String(n)
  }

  const maxTokens = data ? Math.max(...data.timeline.map(t => t.tokens), 1) : 1

  return (
    <div className="h-full flex flex-col p-4 space-y-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <BarChart3 size={14} className="text-accent" />
          Analytics
        </h3>
        <div className="flex items-center gap-2">
          <div className="flex gap-0.5 bg-elevated rounded-lg p-0.5">
            {(['7d', '30d', 'all'] as const).map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`text-[10px] px-2 py-0.5 rounded-md transition-colors ${period === p ? 'bg-accent/15 text-accent' : 'text-text-muted hover:text-text'}`}>
                {p === 'all' ? 'All' : p}
              </button>
            ))}
          </div>
          <button onClick={loadAnalytics} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Loading analytics...</div>
      ) : !data ? (
        <div className="text-xs text-text-muted py-8 text-center">No data available</div>
      ) : (
        <>
          {/* Key metrics */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="flex items-center gap-1.5 mb-1">
                <MessageSquare size={11} className="text-accent" />
                <span className="text-[10px] text-text-muted uppercase">Sessions</span>
              </div>
              <div className="text-lg font-semibold text-text">{data.sessions.recent}</div>
              <div className="text-[9px] text-text-muted">{data.sessions.total} total</div>
            </div>
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="flex items-center gap-1.5 mb-1">
                <Zap size={11} className="text-amber-400" />
                <span className="text-[10px] text-text-muted uppercase">Tokens</span>
              </div>
              <div className="text-lg font-semibold text-text">{formatNumber(data.tokens.total)}</div>
              <div className="text-[9px] text-text-muted">{formatNumber(data.tokens.input)} in / {formatNumber(data.tokens.output)} out</div>
            </div>
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="flex items-center gap-1.5 mb-1">
                <TrendingUp size={11} className="text-green-400" />
                <span className="text-[10px] text-text-muted uppercase">Throughput</span>
              </div>
              <div className="text-lg font-semibold text-text">{data.throughput.avg_tps}</div>
              <div className="text-[9px] text-text-muted">avg tok/s</div>
            </div>
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="flex items-center gap-1.5 mb-1">
                <DollarSign size={11} className="text-green-400" />
                <span className="text-[10px] text-text-muted uppercase">Savings</span>
              </div>
              <div className="text-lg font-semibold text-text">
                {data.costs.savings_usd > 0 ? `$${data.costs.savings_usd.toFixed(4)}` : '—'}
              </div>
              <div className="text-[9px] text-text-muted">vs API pricing</div>
            </div>
          </div>

          {/* Token timeline chart */}
          <div className="bg-elevated border border-border rounded-lg px-3 py-2">
            <div className="text-[10px] text-text-muted uppercase mb-2">Token Usage Over Time</div>
            {data.timeline.length > 0 ? (
              <>
                <div className="flex items-end gap-1 h-20">
                  {data.timeline.map((t, i) => {
                    const h = Math.max((t.tokens / maxTokens) * 76, 2)
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-1">
                        <div
                          className="w-full bg-accent/40 rounded-t transition-all hover:bg-accent"
                          style={{ height: `${h}px` }}
                          title={`${t.date}: ${formatNumber(t.tokens)} tokens, ${t.sessions} sessions`}
                        />
                      </div>
                    )
                  })}
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-[8px] text-text-muted">{data.timeline[0]?.date}</span>
                  <span className="text-[8px] text-text-muted">{data.timeline[data.timeline.length - 1]?.date}</span>
                </div>
              </>
            ) : (
              <div className="text-[10px] text-text-muted text-center py-4">No timeline data</div>
            )}
          </div>

          {/* Cost breakdown */}
          {data.costs.electricity_usd > 0 && (
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] text-text-muted uppercase mb-2">Cost Analysis</div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-text-sec">Electricity (local)</span>
                  <span className="text-[10px] text-text font-mono">${data.costs.electricity_usd.toFixed(6)}</span>
                </div>
                {data.costs.api_comparison_usd > 0 && (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-text-sec">API equivalent</span>
                      <span className="text-[10px] text-text font-mono">${data.costs.api_comparison_usd.toFixed(6)}</span>
                    </div>
                    <div className="flex items-center justify-between border-t border-border/50 pt-1">
                      <span className="text-[10px] text-green-400 font-medium">You saved</span>
                      <span className="text-[10px] text-green-400 font-mono font-medium">${data.costs.savings_usd.toFixed(6)}</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Tool usage */}
          <div className="bg-elevated border border-border rounded-lg px-3 py-2">
            <div className="text-[10px] text-text-muted uppercase mb-2">Tool Usage</div>
            <div className="flex items-center gap-4">
              <div>
                <div className="text-lg font-semibold text-text">{data.tools.total_calls}</div>
                <div className="text-[9px] text-text-muted">total calls</div>
              </div>
              <div className="flex-1 h-3 bg-bg rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 rounded-full transition-all"
                  style={{ width: `${Math.round(data.tools.success_rate * 100)}%` }}
                />
              </div>
              <div className="text-[10px] text-text-sec">{Math.round(data.tools.success_rate * 100)}%</div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function generateTimeline(sessions: any[], period: string): { date: string; sessions: number; tokens: number }[] {
  const days = period === '7d' ? 7 : period === '30d' ? 30 : 90
  const timeline: { date: string; sessions: number; tokens: number }[] = []

  for (let i = days - 1; i >= 0; i--) {
    const date = new Date()
    date.setDate(date.getDate() - i)
    const dateStr = date.toISOString().slice(0, 10)

    const daySessions = sessions.filter((s: any) => {
      const d = new Date(s.updated || s.created)
      return d.toISOString().slice(0, 10) === dateStr
    }).length

    timeline.push({
      date: dateStr.slice(5), // MM-DD
      sessions: daySessions,
      tokens: daySessions * 500, // estimate
    })
  }

  return timeline
}
