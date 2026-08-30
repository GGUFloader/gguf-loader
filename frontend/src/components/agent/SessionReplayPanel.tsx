import { useState, useEffect, useCallback } from 'react'
import { Play, Pause, SkipForward, SkipBack, RotateCcw, FileText, Clock, ChevronRight, ChevronDown, Wrench, MessageSquare } from 'lucide-react'
import { agentApi } from '../../api/client'

interface ReplayStep {
  index: number
  action: string // "user_message" | "agent_response" | "tool_call" | "tool_result"
  data: Record<string, any>
  timestamp: number
}

interface ReplaySession {
  filename: string
  session_id: string
  title: string
  steps: number
  stepsData?: ReplayStep[]
}

interface ExportSession {
  filename: string
  title: string
  exported_at: string
  message_count: number
}

const STEP_ICONS: Record<string, any> = {
  user_message: MessageSquare,
  agent_response: MessageSquare,
  tool_call: Wrench,
  tool_result: Wrench,
}

const STEP_COLORS: Record<string, string> = {
  user_message: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  agent_response: 'text-accent bg-accent/10 border-accent/20',
  tool_call: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  tool_result: 'text-green-400 bg-green-500/10 border-green-500/20',
}

export function SessionReplayPanel() {
  const [replays, setReplays] = useState<ReplaySession[]>([])
  const [exports, setExports] = useState<ExportSession[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedReplay, setSelectedReplay] = useState<ReplaySession | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [activeTab, setActiveTab] = useState<'replays' | 'exports'>('replays')
  const [expandedStep, setExpandedStep] = useState<number | null>(null)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [r, e] = await Promise.all([agentApi.replays(), agentApi.exports()])
      setReplays(r)
      setExports(e)
    } catch {}
    setLoading(false)
  }

  const selectReplay = useCallback((r: ReplaySession) => {
    setSelectedReplay(r)
    setCurrentStep(0)
    setPlaying(false)
    setExpandedStep(null)
  }, [])

  // Auto-play through steps
  useEffect(() => {
    if (!playing || !selectedReplay) return
    const total = selectedReplay.steps || 0
    if (currentStep >= total - 1) {
      setPlaying(false)
      return
    }
    const timer = setTimeout(() => setCurrentStep(s => s + 1), 800)
    return () => clearTimeout(timer)
  }, [playing, currentStep, selectedReplay])



  return (
    <div className="h-full flex flex-col p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <RotateCcw size={14} className="text-accent" />
          Session Replay
        </h3>
        <button onClick={loadData} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RotateCcw size={13} />
        </button>
      </div>

      {/* Tab selector */}
      <div className="flex gap-1 bg-elevated rounded-lg p-0.5">
        <button
          onClick={() => setActiveTab('replays')}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'replays' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}
        >
          Replays ({replays.length})
        </button>
        <button
          onClick={() => setActiveTab('exports')}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'exports' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}
        >
          Exports ({exports.length})
        </button>
      </div>

      {/* If a replay is selected, show the step-through view */}
      {selectedReplay ? (
        <div className="flex-1 flex flex-col min-h-0 space-y-3">
          {/* Back + title */}
          <button onClick={() => setSelectedReplay(null)} className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors">
            <ChevronRight size={12} className="rotate-180" />
            Back to list
          </button>
          <div className="text-xs font-medium text-text truncate">{selectedReplay.title || selectedReplay.filename}</div>

          {/* Playback controls */}
          <div className="flex items-center gap-2 bg-elevated rounded-lg px-3 py-2">
            <button onClick={() => setCurrentStep(Math.max(0, currentStep - 1))} disabled={currentStep === 0}
              className="p-1 text-text-muted hover:text-text disabled:opacity-30 transition-colors">
              <SkipBack size={14} />
            </button>
            <button onClick={() => setPlaying(!playing)}
              className="p-1.5 bg-accent/15 text-accent rounded-md hover:bg-accent/25 transition-colors">
              {playing ? <Pause size={14} /> : <Play size={14} />}
            </button>
            <button onClick={() => setCurrentStep(Math.min((selectedReplay.steps || 1) - 1, currentStep + 1))}
              disabled={currentStep >= (selectedReplay.steps || 1) - 1}
              className="p-1 text-text-muted hover:text-text disabled:opacity-30 transition-colors">
              <SkipForward size={14} />
            </button>
            <div className="flex-1 text-[10px] text-text-muted text-center">
              Step {currentStep + 1} / {selectedReplay.steps || 0}
            </div>
          </div>

          {/* Step list — show all steps up to current */}
          <div className="flex-1 overflow-y-auto space-y-1.5">
            {Array.from({ length: Math.min(currentStep + 1, selectedReplay.steps || 0) }, (_, i) => {
              const action = 'user_message' // We don't have step data from the list endpoint, show placeholders
              const Icon = STEP_ICONS[action] || FileText
              const colorClass = STEP_COLORS[action] || 'text-text-muted bg-elevated border-border'
              const isExpanded = expandedStep === i
              return (
                <div key={i} className={`border rounded-lg transition-all ${colorClass} ${i === currentStep ? 'ring-1 ring-accent/50' : 'opacity-70'}`}>
                  <button
                    onClick={() => setExpandedStep(isExpanded ? null : i)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-left"
                  >
                    <Icon size={12} />
                    <span className="text-[10px] font-medium flex-1">Step {i + 1}</span>
                    <Clock size={10} className="opacity-50" />
                    {isExpanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                  </button>
                  {isExpanded && (
                    <div className="px-3 pb-2 text-[10px] text-text-sec/80 font-mono whitespace-pre-wrap break-all">
                      Step details available in full replay data
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ) : loading ? (
        <div className="text-xs text-text-muted py-8 text-center">Loading replays...</div>
      ) : activeTab === 'replays' ? (
        replays.length === 0 ? (
          <div className="text-center py-8 text-text-muted text-xs">
            <RotateCcw size={24} className="mx-auto mb-2 opacity-30" />
            <p>No replays yet</p>
            <p className="mt-1 text-text-muted/50">Replays are saved when you run agent sessions</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto space-y-1.5">
            {replays.map((r) => (
              <button key={r.filename} onClick={() => selectReplay(r)}
                className="w-full text-left bg-elevated border border-border rounded-lg p-3 hover:border-accent/30 transition-colors group">
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-text truncate">{r.title || r.filename}</div>
                    <div className="text-[10px] text-text-muted mt-0.5">{r.steps} steps · {r.session_id.slice(0, 8)}</div>
                  </div>
                  <Play size={12} className="text-text-muted group-hover:text-accent transition-colors" />
                </div>
              </button>
            ))}
          </div>
        )
      ) : (
        exports.length === 0 ? (
          <div className="text-center py-8 text-text-muted text-xs">
            <FileText size={24} className="mx-auto mb-2 opacity-30" />
            <p>No exports yet</p>
            <p className="mt-1 text-text-muted/50">Export sessions from the agent API</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto space-y-1.5">
            {exports.map((e) => (
              <div key={e.filename} className="bg-elevated border border-border rounded-lg p-3">
                <div className="text-xs font-medium text-text">{e.title || e.filename}</div>
                <div className="flex items-center gap-2 text-[10px] text-text-muted mt-0.5">
                  <span>{e.message_count} messages</span>
                  {e.exported_at && <span>· {e.exported_at}</span>}
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}
