import { useEffect, useRef } from 'react'
import { Bell, Check, CheckCheck, Trash2, X, Bot, AlertTriangle, Info, Zap } from 'lucide-react'
import { useNotificationStore, type Notification, type NotificationType } from '../../stores/notificationStore'

const TYPE_ICONS: Record<NotificationType, any> = {
  info: Info,
  success: Check,
  warning: AlertTriangle,
  error: AlertTriangle,
  agent: Bot,
  system: Zap,
}

const TYPE_COLORS: Record<NotificationType, string> = {
  info: 'text-blue-400 bg-blue-500/10',
  success: 'text-green-400 bg-green-500/10',
  warning: 'text-amber-400 bg-amber-500/10',
  error: 'text-red-400 bg-red-500/10',
  agent: 'text-accent bg-accent/10',
  system: 'text-purple-400 bg-purple-500/10',
}

function formatTime(ts: number): string {
  const diff = Date.now() - ts
  if (diff < 60_000) return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return new Date(ts).toLocaleDateString()
}

function NotificationItem({ notification }: { notification: Notification }) {
  const { markRead, dismiss } = useNotificationStore()
  const Icon = TYPE_ICONS[notification.type] || Info
  const colorClass = TYPE_COLORS[notification.type] || TYPE_COLORS.info

  return (
    <div
      className={`flex items-start gap-2.5 px-3 py-2.5 border-b border-border/50 transition-colors ${
        notification.read ? 'opacity-60' : 'bg-accent/5'
      }`}
      onClick={() => !notification.read && markRead(notification.id)}
    >
      <div className={`p-1.5 rounded-lg flex-shrink-0 ${colorClass}`}>
        <Icon size={12} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium text-text truncate">{notification.title}</span>
          {!notification.read && <div className="w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />}
        </div>
        <div className="text-[10px] text-text-muted mt-0.5 line-clamp-2">{notification.message}</div>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[9px] text-text-muted">{formatTime(notification.timestamp)}</span>
          {notification.action && (
            <button
              onClick={(e) => { e.stopPropagation(); notification.action!.onClick() }}
              className="text-[9px] text-accent hover:text-accent-hover transition-colors"
            >
              {notification.action.label}
            </button>
          )}
        </div>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); dismiss(notification.id) }}
        className="p-1 text-text-muted hover:text-text transition-colors flex-shrink-0"
        aria-label="Dismiss notification"
      >
        <X size={11} />
      </button>
    </div>
  )
}

export function NotificationPanel() {
  const { notifications, unreadCount, panelOpen, markAllRead, clearAll, closePanel } = useNotificationStore()
  const panelRef = useRef<HTMLDivElement>(null)

  // Close on click outside
  useEffect(() => {
    if (!panelOpen) return
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        closePanel()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [panelOpen, closePanel])

  if (!panelOpen) return null

  return (
    <div
      ref={panelRef}
      className="fixed top-14 right-4 w-80 max-h-[70vh] bg-surface border border-border rounded-xl shadow-2xl z-50 flex flex-col animate-slide-up"
      role="dialog"
      aria-label="Notifications"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Bell size={14} className="text-accent" />
          <span className="text-xs font-semibold text-text">Notifications</span>
          {unreadCount > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 bg-accent text-onAccent rounded-full font-medium">
              {unreadCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {unreadCount > 0 && (
            <button onClick={markAllRead} className="p-1.5 text-text-muted hover:text-accent rounded transition-colors" title="Mark all read">
              <CheckCheck size={13} />
            </button>
          )}
          {notifications.length > 0 && (
            <button onClick={clearAll} className="p-1.5 text-text-muted hover:text-red-400 rounded transition-colors" title="Clear all">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Notifications list */}
      <div className="flex-1 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <Bell size={24} className="mx-auto mb-2 text-text-muted/30" />
            <p className="text-xs text-text-muted">No notifications</p>
          </div>
        ) : (
          notifications.map(n => (
            <NotificationItem key={n.id} notification={n} />
          ))
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-border text-center">
        <span className="text-[9px] text-text-muted">
          {notifications.length} notification{notifications.length !== 1 ? 's' : ''}
        </span>
      </div>
    </div>
  )
}

/**
 * Bell icon button that toggles the notification panel.
 * Place this in the Header component.
 */
export function NotificationBell() {
  const { unreadCount, togglePanel } = useNotificationStore()

  return (
    <button
      onClick={togglePanel}
      className="relative p-1.5 hover:bg-elevated rounded-lg transition-colors"
      aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
    >
      <Bell size={18} className="text-text-sec" />
      {unreadCount > 0 && (
        <div className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-danger text-white text-[7px] font-bold rounded-full flex items-center justify-center">
          {unreadCount > 9 ? '9+' : unreadCount}
        </div>
      )}
    </button>
  )
}
