import { useState, useEffect } from 'react'
import { Activity, Zap, AlertTriangle, RefreshCw, BarChart3, ArrowRight } from 'lucide-react'
import { agentApi } from '../../api/client'

interface StepData {
  index: number
  action: string
  tool_name: string
  duration_ms: number
  input_tokens: number
  output_tokens: number
  tokens_per_second: number
  success: boolean
  error: string
}

interface RunProfile {
  run_id: string
  total_duration_ms: number
  step_count: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  tokens_per_second: number
  llm_time_ms: number
  tool_time_ms: number
  approval_time_ms: number
  tool_success_rate: number
  bottleneck: StepData | null
}

interface ThroughputPoint {
  tps: number
  timestamp: number
}

interface BottleneckAnalysis {
  total_runs: number
  total_steps: number
  time_breakdown: { llm_ms: number; tool_ms: number; approval_ms: number; llm_pct: number; tool_pct: number }
  bottlenecks: { type: string; action?: string; tool?: string; avg_ms: number; count?: number }[]
  suggestions: string[]
}

const ACTION_COLORS: Record<string, string> = {
  llm_call: 'bg-blue-500',
  tool_execute: 'bg-amber-500',
  approval_wait: 'bg-purple-500',
  planning: 'bg-cyan-500',
  final_answer: 'bg-green-500',
}

const ACTION_LABELS: Record<string, string> = {
  llm_call: 'LLM',
  tool_execute: 'Tool',
  approval_wait: 'Wait',
  planning: 'Plan',
  final_answer: 'Done',
}

export function ProfilingPanel() {
  const [history, setHistory] = useState<RunProfile[]>([])
  const [breakdown, setBreakdown] = useState<any[]>([])
  const [bottlenecks, setBottlenecks] = useState<BottleneckAnalysis | null>(null)
  const [throughput, setThroughput] = useState<ThroughputPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedRun, setSelectedRun] = useState<number | null>(null)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [h, b, bn, tp] = await Promise.all([
        agentApi.profileHistory(10),
        agentApi.profileSteps(3),
        agentApi.profileBottlenecks(),
        agentApi.profileThroughput(),
      ])
      setHistory(h)
      setBreakdown(b)
      setBottlenecks(bn)
      setThroughput(tp)
    } catch {}
    setLoading(false)
  }

  function formatMs(ms: number) {
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const latestRun = history.length > 0 ? history[history.length - 1] : null
  const latestBreakdown = breakdown.length > 0 ? breakdown[breakdown.length - 1] : null

  return (
    <div className="h-full flex flex-col p-4 space-y-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Activity size={14} className="text-accent" />
          Profiling
        </h3>
        <button onClick={loadData} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Loading profiling data...</div>
      ) : history.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-xs">
          <BarChart3 size={24} className="mx-auto mb-2 opacity-30" />
          <p>No profiling data yet</p>
          <p className="mt-1 text-text-muted/50">Run an agent session to see performance data</p>
        </div>
      ) : (
        <>
          {/* Quick stats */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] text-text-muted uppercase">Last Run</div>
              <div className="text-lg font-semibold text-text">{latestRun ? formatMs(latestRun.total_duration_ms) : '-'}</div>
              <div className="text-[10px] text-text-muted">{latestRun?.step_count || 0} steps</div>
            </div>
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] text-text-muted uppercase">Throughput</div>
              <div className="text-lg font-semibold text-text">{latestRun?.tokens_per_second || 0}</div>
              <div className="text-[10px] text-text-muted">tokens/sec</div>
            </div>
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] text-text-muted uppercase">Tokens</div>
              <div className="text-lg font-semibold text-text">{latestRun?.total_tokens || 0}</div>
              <div className="text-[10px] text-text-muted">{latestRun?.total_input_tokens || 0} in / {latestRun?.total_output_tokens || 0} out</div>
            </div>
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] text-text-muted uppercase">Tool Success</div>
              <div className="text-lg font-semibold text-text">{latestRun ? Math.round(latestRun.tool_success_rate * 100) : 0}%</div>
            </div>
          </div>

          {/* Time breakdown bar */}
          {bottlenecks?.time_breakdown && (
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] text-text-muted uppercase mb-2">Time Breakdown</div>
              <div className="flex h-4 rounded-full overflow-hidden bg-bg">
                {bottlenecks.time_breakdown.llm_pct > 0 && (
                  <div
                    className="bg-blue-500 h-full transition-all"
                    style={{ width: `${bottlenecks.time_breakdown.llm_pct}%` }}
                    title={`LLM: ${bottlenecks.time_breakdown.llm_ms}ms (${bottlenecks.time_breakdown.llm_pct}%)`}
                  />
                )}
                {bottlenecks.time_breakdown.tool_pct > 0 && (
                  <div
                    className="bg-amber-500 h-full transition-all"
                    style={{ width: `${bottlenecks.time_breakdown.tool_pct}%` }}
                    title={`Tools: ${bottlenecks.time_breakdown.tool_ms}ms`}
                  />
                )}
              </div>
              <div className="flex items-center gap-3 mt-1.5">
                <span className="text-[9px] flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /> LLM {bottlenecks.time_breakdown.llm_pct}%</span>
                <span className="text-[9px] flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Tools {bottlenecks.time_breakdown.tool_pct}%</span>
                {bottlenecks.time_breakdown.approval_ms > 0 && (
                  <span className="text-[9px] flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-500" /> Approval {Math.round(bottlenecks.time_breakdown.approval_ms)}ms</span>
                )}
              </div>
            </div>
          )}

          {/* Bottleneck alerts */}
          {bottlenecks && bottlenecks.bottlenecks.length > 0 && (
            <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg px-3 py-2">
              <div className="text-[10px] text-amber-400 uppercase font-medium mb-1.5 flex items-center gap-1">
                <AlertTriangle size={11} /> Bottlenecks Detected
              </div>
              {bottlenecks.bottlenecks.map((b, i) => (
                <div key={i} className="text-[10px] text-text-sec mb-1">
                  {b.type === 'slow_action' && `Slow ${ACTION_LABELS[b.action || ''] || b.action}: avg ${formatMs(b.avg_ms)}`}
                  {b.type === 'slow_tool' && `Slow tool "${b.tool}": avg ${formatMs(b.avg_ms)}`}
                  {b.type === 'approval_bottleneck' && `Approval waits: ${formatMs(b.avg_ms)} avg`}
                </div>
              ))}
              {bottlenecks.suggestions.length > 0 && (
                <div className="mt-1.5 space-y-0.5">
                  {bottlenecks.suggestions.map((s, i) => (
                    <div key={i} className="text-[9px] text-accent flex items-start gap-1">
                      <ArrowRight size={8} className="mt-0.5 flex-shrink-0" /> {s}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step timeline (latest run) */}
          {latestBreakdown && latestBreakdown.steps.length > 0 && (
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] text-text-muted uppercase mb-2">Step Timeline (Latest Run)</div>
              <div className="space-y-1">
                {latestBreakdown.steps.map((step: StepData, i: number) => {
                  const maxMs = Math.max(...latestBreakdown.steps.map((s: StepData) => s.duration_ms), 1)
                  const pct = (step.duration_ms / maxMs) * 100
                  return (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-[9px] text-text-muted w-12 text-right">{formatMs(step.duration_ms)}</span>
                      <div className="flex-1 h-3 bg-bg rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${ACTION_COLORS[step.action] || 'bg-gray-500'} ${!step.success ? 'opacity-50' : ''}`}
                          style={{ width: `${Math.max(pct, 3)}%` }}
                        />
                      </div>
                      <span className="text-[9px] text-text-sec w-20 truncate">
                        {ACTION_LABELS[step.action] || step.action}
                        {step.tool_name ? `: ${step.tool_name}` : ''}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Throughput mini-chart */}
          {throughput.length > 0 && (
            <div className="bg-elevated border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] text-text-muted uppercase mb-2 flex items-center gap-1">
                <Zap size={10} /> Throughput History
              </div>
              <div className="flex items-end gap-1 h-12">
                {throughput.slice(-15).map((pt, i) => {
                  const maxTps = Math.max(...throughput.map(p => p.tps), 1)
                  const h = Math.max((pt.tps / maxTps) * 48, 2)
                  return (
                    <div
                      key={i}
                      className="flex-1 bg-accent/40 rounded-t transition-all hover:bg-accent"
                      style={{ height: `${h}px` }}
                      title={`${pt.tps.toFixed(1)} tok/s`}
                    />
                  )
                })}
              </div>
              <div className="text-[9px] text-text-muted text-center mt-1">
                Last {throughput.length} LLM calls
              </div>
            </div>
          )}

          {/* Run history */}
          <div>
            <div className="text-[10px] text-text-muted uppercase mb-2">Run History</div>
            <div className="space-y-1">
              {history.slice().reverse().map((run, i) => (
                <div
                  key={i}
                  onClick={() => setSelectedRun(selectedRun === i ? null : i)}
                  className="bg-elevated border border-border rounded-lg px-3 py-1.5 cursor-pointer hover:border-accent/30 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-text truncate flex-1">{run.run_id.slice(0, 20)}</span>
                    <span className="text-[9px] text-text-muted ml-2">{formatMs(run.total_duration_ms)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[9px] text-text-muted mt-0.5">
                    <span>{run.step_count} steps</span>
                    <span>{run.total_tokens} tokens</span>
                    <span>{run.tokens_per_second} tok/s</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
