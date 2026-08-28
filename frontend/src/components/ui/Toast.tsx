import { X, CheckCircle2, XCircle, AlertTriangle, Info } from 'lucide-react'
import { useToastStore, type ToastType } from '../../stores/toastStore'

const ICONS: Record<ToastType, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const COLORS: Record<ToastType, string> = {
  success: 'bg-green-500/15 border-green-500/30 text-green-400',
  error: 'bg-red-500/15 border-red-500/30 text-red-400',
  warning: 'bg-yellow-500/15 border-yellow-500/30 text-yellow-400',
  info: 'bg-blue-500/15 border-blue-500/30 text-blue-400',
}

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore()

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => {
        const Icon = ICONS[t.type]
        return (
          <div
            key={t.id}
            className={`flex items-start gap-2.5 px-4 py-3 rounded-xl border shadow-lg backdrop-blur-sm animate-slide-in ${COLORS[t.type]}`}
          >
            <Icon size={16} className="flex-shrink-0 mt-0.5" />
            <span className="text-sm text-text flex-1">{t.message}</span>
            <button
              onClick={() => removeToast(t.id)}
              className="flex-shrink-0 text-text-muted hover:text-text transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
