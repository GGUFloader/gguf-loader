import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, CheckCircle2, Loader2, Sparkles, X,
} from 'lucide-react'
import { appApi, modelApi } from '../../api/client'
import type { AppInfo, ModelInfo } from '../../api/types'

const DONE_KEY = 'ggufloader_compat_check_done'
const POLL_MS = 1200
const MAX_POLLS = 12

const FALLBACK_APP: AppInfo = {
  name: 'GGUF Loader',
  version: '',
  label: 'Gemma 4 12B Q4_K_M',
  tagline: 'Optimized for Gemma 4 12B Q4_K_M',
  pinned: { arch: 'gemma4', quant: 'Q4_K_M', size: '12B' },
}

type Status = 'checking' | 'ready' | 'missing'

/**
 * First-launch model-compatibility check.
 *
 * Shows once per install (localStorage flag) and verifies the loaded
 * model against the pinned Gemma 4 12B Q4_K_M target. While the startup
 * auto-loader is still scanning/loading it polls /api/model/info, then
 * presents either a green "ready" card or guidance on where to place the
 * GGUF. Any explicit dismissal marks the check as done.
 */
export function CompatibilityDialog() {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<Status>('checking')
  const [info, setInfo] = useState<ModelInfo | null>(null)
  const [app, setApp] = useState<AppInfo>(FALLBACK_APP)
  const [phase, setPhase] = useState<string | undefined>()
  const mounted = useRef(true)

  const markDone = useCallback(() => {
    try { localStorage.setItem(DONE_KEY, '1') } catch { /* ignore */ }
    setOpen(false)
  }, [])

  const settle = useCallback((i: ModelInfo) => {
    if (!mounted.current) return
    setInfo(i)
    if (i.loaded && i.compatible !== false) {
      // Model present and compatible: nothing to check. Mark done and
      // never surface the dialog on the happy path.
      try { localStorage.setItem(DONE_KEY, '1') } catch { /* ignore */ }
      setStatus('ready')
      setOpen(false)
      return
    }
    setStatus('missing')
  }, [])

  const runCheck = useCallback(async () => {
    if (!mounted.current) return
    setStatus('checking')
    try {
      const d = await appApi.info()
      if (mounted.current) setApp(d)
    } catch { /* offline fallback */ }

    let polls = 0
    for (;;) {
      let i: ModelInfo
      try {
        i = await modelApi.info()
      } catch {
        if (!mounted.current) return
        setInfo(null)
        setStatus('missing')
        return
      }
      if (!mounted.current) return
      setPhase(i.auto_load)
      const pending = !i.loaded &&
        (i.auto_load === 'scanning' || i.auto_load === 'loading')
      if (!pending || polls >= MAX_POLLS) {
        settle(i)
        return
      }
      polls += 1
      await new Promise((r) => setTimeout(r, POLL_MS))
    }
  }, [settle])

  useEffect(() => {
    mounted.current = true
    let shown = false
    try { shown = !!localStorage.getItem(DONE_KEY) } catch { /* ignore */ }
    if (shown) {
      mounted.current = false
      return
    }
    let alive = true
    ;(async () => {
      // Fast path: the model is already loaded & compatible at mount, so
      // the check has nothing to report — acknowledge silently, no flash.
      let pre: ModelInfo | null = null
      try { pre = await modelApi.info() } catch { /* offline */ }
      if (!alive) return
      if (pre && pre.loaded && pre.compatible !== false) {
        try { localStorage.setItem(DONE_KEY, '1') } catch { /* ignore */ }
        mounted.current = false
        return
      }
      // Something needs attention (missing / incompatible / still loading) —
      // show the dialog and poll until it settles.
      setOpen(true)
      await runCheck()
    })()
    return () => { alive = false; mounted.current = false }
  }, [runCheck])

  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-surface border border-border rounded-xl shadow-2xl w-[520px] max-h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-accent" />
            <div>
              <h2 className="text-base font-semibold text-text">Welcome to {app.name}</h2>
              <p className="text-[11px] text-text-muted">Model compatibility check</p>
            </div>
          </div>
          <button onClick={markDone}
            className="p-1.5 text-text-muted hover:text-text rounded-lg hover:bg-elevated transition-colors"
            aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {status === 'checking' && (
            <div className="flex items-start gap-3">
              <Loader2 size={18} className="text-accent animate-spin mt-0.5 shrink-0" />
              <div className="space-y-1.5">
                <p className="text-sm text-text">Checking model compatibility…</p>
                <p className="text-xs text-text-muted leading-relaxed">
                  {phase === 'scanning' && 'Scanning the models folder for a compatible GGUF…'}
                  {phase === 'loading' && 'Loading the pinned model in the background…'}
                  {phase && phase !== 'scanning' && phase !== 'loading' &&
                    `Current state: ${phase}.`}
                  {!phase && 'Contacting the model service…'}
                </p>
              </div>
            </div>
          )}

          {status === 'ready' && (
            <div className="flex items-start gap-3">
              <CheckCircle2 size={20} className="text-green-400 mt-0.5 shrink-0" />
              <div className="space-y-1.5">
                <p className="text-sm font-medium text-text">Model ready</p>
                <p className="text-xs text-text-sec leading-relaxed">
                  {info?.filename
                    ? <><span className="font-mono text-text">{info.filename}</span> is loaded and
                      matches the pinned target.</>
                    : 'A compatible model is loaded.'}{' '}
                  This build of {app.name} is {app.tagline.toLowerCase()}.
                </p>
              </div>
            </div>
          )}

          {status === 'missing' && (
            <div className="flex items-start gap-3">
              <AlertTriangle size={20} className="text-amber-400 mt-0.5 shrink-0" />
              <div className="space-y-2 flex-1">
                <p className="text-sm font-medium text-text">Model needed</p>
                <p className="text-xs text-text-sec leading-relaxed">
                  This build runs only on <span className="text-text">{app.label}</span> (Q4_K_M).
                  No compatible model is loaded yet.
                </p>
                {info?.auto_load_message && (
                  <p className="text-xs text-amber-300/90 leading-relaxed">
                    {info.auto_load_message}
                  </p>
                )}
                {info?.models_dir && (
                  <div className="space-y-1">
                    <p className="text-[11px] text-text-muted">
                      Place your Gemma 4 12B Q4_K_M <span className="font-mono">.gguf</span> here —
                      it will be detected and loaded automatically:
                    </p>
                    <div className="px-3 py-2 bg-elevated border border-border rounded-lg font-mono text-[11px] text-accent break-all">
                      {info.models_dir}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border">
          {status === 'missing' && (
            <button onClick={runCheck}
              className="px-4 py-2 text-sm text-text-sec hover:text-text rounded-lg hover:bg-elevated transition-colors">
              Check again
            </button>
          )}
          <button onClick={markDone}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-onAccent rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors">
            {status === 'checking' ? 'Close' : 'Continue'}
          </button>
        </div>
      </div>
    </div>
  )
}