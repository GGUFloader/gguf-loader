import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { appApi } from '../../api/client'
import type { AppInfo } from '../../api/types'

// Shown immediately (offline-safe) until /api/app/info answers; the
// backend copy in ggufloader/config.py is the source of truth.
const FALLBACK: AppInfo = {
  name: 'GGUF Loader',
  version: '',
  label: 'Gemma 4 12B Q4_K_M',
  tagline: 'Optimized for Gemma 4 12B Q4_K_M',
  pinned: { arch: 'gemma4', quant: 'Q4_K_M', size: '12B' },
}

export function VersionBanner() {
  const [info, setInfo] = useState<AppInfo>(FALLBACK)

  useEffect(() => {
    let alive = true
    appApi.info()
      .then((d) => { if (alive) setInfo(d) })
      .catch(() => { /* keep offline fallback */ })
    return () => { alive = false }
  }, [])

  return (
    <div role="status"
      className="flex items-center gap-2 px-4 h-7 bg-accent/5 border-b border-border text-[11px] text-text-sec select-none overflow-hidden">
      <Sparkles size={11} className="text-accent shrink-0" />
      <span className="truncate">
        <span className="text-text font-medium">{info.name}</span>
        {info.version && <span className="text-text-muted"> v{info.version}</span>}
        <span className="text-text-muted"> · </span>
        <span className="text-accent font-medium">{info.tagline}</span>
      </span>
    </div>
  )
}