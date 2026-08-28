import { useChatStore } from '../../stores/chatStore'
import { Target, ListChecks, Play, Search, RefreshCw, CheckCircle2, Circle, Check, X, Loader2 } from 'lucide-react'

const PHASE_META: Record<string, { icon: typeof Target; label: string; color: string }> = {
  goal: { icon: Target, label: 'Goal', color: 'text-blue-400' },
  plan: { icon: ListChecks, label: 'Planning', color: 'text-purple-400' },
  execute: { icon: Play, label: 'Executing', color: 'text-green-400' },
  verify: { icon: Search, label: 'Verifying', color: 'text-yellow-400' },
  continue: { icon: RefreshCw, label: 'Replanning', color: 'text-orange-400' },
  finish: { icon: CheckCircle2, label: 'Finishing', color: 'text-emerald-400' },
}

const STEP_STATUS_ICON: Record<string, typeof Circle> = {
  pending: Circle,
  running: Loader2,
  done: Check,
  failed: X,
}

const STEP_STATUS_COLOR: Record<string, string> = {
  pending: 'text-text-muted',
  running: 'text-blue-400 animate-pulse',
  done: 'text-green-400',
  failed: 'text-red-400',
}

export function PlanTracker() {
  const { plan } = useChatStore()
  const { phase, goal, plan: steps, planStep, phaseLog } = plan

  // Don't show if idle and no plan
  if (phase === 'idle' && steps.length === 0) return null

  return (
    <div className="w-full border-b border-border bg-surface/80 backdrop-blur-sm">
      <div className="max-w-3xl mx-auto px-4 py-3 space-y-2">
        {/* Goal */}
        {goal && (
          <div className="flex items-start gap-2">
            <Target size={14} className="text-blue-400 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <span className="text-[10px] font-medium text-blue-400 uppercase tracking-wider">Goal</span>
              <p className="text-xs text-text mt-0.5 leading-relaxed">{goal}</p>
            </div>
          </div>
        )}

        {/* Phase indicators */}
        {phase !== 'idle' && (
          <div className="flex items-center gap-3 flex-wrap">
            {(['goal', 'plan', 'execute', 'verify', 'finish'] as const).map((p) => {
              const meta = PHASE_META[p]
              if (!meta) return null
              const Icon = meta.icon
              const isActive = phase === p
              const isDone = isPhaseDone(phase, p)
              return (
                <div
                  key={p}
                  className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] transition-all ${
                    isActive
                      ? 'bg-accent/20 border border-accent/40'
                      : isDone
                        ? 'bg-green-500/10 border border-green-500/20'
                        : 'bg-elevated border border-border opacity-50'
                  }`}
                >
                  <Icon size={10} className={`${isActive ? meta.color : isDone ? 'text-green-400' : 'text-text-muted'}`} />
                  <span className={`font-medium ${isActive ? 'text-text' : isDone ? 'text-green-400' : 'text-text-muted'}`}>
                    {meta.label}
                  </span>
                  {isDone && <Check size={8} className="text-green-400" />}
                </div>
              )
            })}
          </div>
        )}

        {/* Plan steps (shown during execute phase) */}
        {steps.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] font-medium text-text-muted uppercase tracking-wider">
              Plan ({steps.length} steps)
            </span>
            <div className="space-y-0.5">
              {steps.map((step) => {
                const StatusIcon = STEP_STATUS_ICON[step.status] || Circle
                return (
                  <div
                    key={step.step}
                    className={`flex items-center gap-2 px-2 py-1 rounded text-xs ${
                      step.status === 'running' ? 'bg-accent/5' : ''
                    }`}
                  >
                    <StatusIcon
                      size={12}
                      className={`flex-shrink-0 ${STEP_STATUS_COLOR[step.status]} ${
                        step.status === 'running' ? 'animate-spin' : ''
                      }`}
                    />
                    <span className="text-text-muted w-4 text-right">{step.step}.</span>
                    <span className={`flex-1 ${
                      step.status === 'done'
                        ? 'text-green-400 line-through opacity-70'
                        : step.status === 'failed'
                          ? 'text-red-400'
                          : step.status === 'running'
                            ? 'text-text'
                            : 'text-text-sec'
                    }`}>
                      {step.description}
                    </span>
                    {step.status === 'done' && step.result && (
                      <span className="text-[10px] text-green-400/60 truncate max-w-[120px]">
                        {step.result.slice(0, 40)}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Current step progress (during execution) */}
        {planStep && (
          <div className="flex items-center gap-2 text-[10px] text-text-muted">
            <Loader2 size={10} className="animate-spin text-accent" />
            <span>
              Step {planStep.current}/{planStep.total}: {planStep.description}
            </span>
          </div>
        )}

        {/* Phase log (collapsed, expandable) */}
        {phaseLog.length > 0 && phase === 'idle' && (
          <details className="group">
            <summary className="text-[10px] text-text-muted cursor-pointer hover:text-text transition-colors">
              Phase log ({phaseLog.length} entries)
            </summary>
            <div className="mt-1 space-y-0.5 max-h-32 overflow-y-auto">
              {phaseLog.map((entry, i) => (
                <div key={i} className="text-[10px] text-text-muted pl-2 border-l border-border">
                  {entry}
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  )
}

function isPhaseDone(current: string, target: string): boolean {
  const order = ['goal', 'plan', 'execute', 'verify', 'continue', 'finish']
  return order.indexOf(current) > order.indexOf(target)
}
