import { create } from 'zustand'

export type NotificationType = 'info' | 'success' | 'warning' | 'error' | 'agent' | 'system'

export interface Notification {
  id: string
  type: NotificationType
  title: string
  message: string
  timestamp: number
  read: boolean
  action?: {
    label: string
    onClick: () => void
  }
  metadata?: Record<string, any>
}

interface NotificationState {
  notifications: Notification[]
  unreadCount: number
  panelOpen: boolean
  add: (type: NotificationType, title: string, message: string, options?: { action?: Notification['action']; metadata?: Record<string, any> }) => string
  markRead: (id: string) => void
  markAllRead: () => void
  dismiss: (id: string) => void
  clearAll: () => void
  togglePanel: () => void
  openPanel: () => void
  closePanel: () => void
}

let counter = 0

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  panelOpen: false,

  add: (type, title, message, options) => {
    const id = `notif_${++counter}_${Date.now()}`
    const notification: Notification = {
      id,
      type,
      title,
      message,
      timestamp: Date.now(),
      read: false,
      ...options,
    }
    set((s) => ({
      notifications: [notification, ...s.notifications].slice(0, 100),
      unreadCount: s.unreadCount + 1,
    }))

    // Auto-persist
    try {
      const all = get().notifications
      localStorage.setItem('ggufloader_notifications', JSON.stringify(all.slice(0, 50)))
    } catch {}

    return id
  },

  markRead: (id) => {
    set((s) => {
      const notifications = s.notifications.map(n =>
        n.id === id ? { ...n, read: true } : n
      )
      return {
        notifications,
        unreadCount: notifications.filter(n => !n.read).length,
      }
    })
  },

  markAllRead: () => {
    set((s) => ({
      notifications: s.notifications.map(n => ({ ...n, read: true })),
      unreadCount: 0,
    }))
  },

  dismiss: (id) => {
    set((s) => {
      const notifications = s.notifications.filter(n => n.id !== id)
      return {
        notifications,
        unreadCount: notifications.filter(n => !n.read).length,
      }
    })
  },

  clearAll: () => set({ notifications: [], unreadCount: 0 }),

  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  openPanel: () => set({ panelOpen: true }),
  closePanel: () => set({ panelOpen: false }),
}))

// Notification helpers
export const notify = {
  info: (title: string, message: string) => useNotificationStore.getState().add('info', title, message),
  success: (title: string, message: string) => useNotificationStore.getState().add('success', title, message),
  warning: (title: string, message: string) => useNotificationStore.getState().add('warning', title, message),
  error: (title: string, message: string) => useNotificationStore.getState().add('error', title, message),
  agent: (title: string, message: string) => useNotificationStore.getState().add('agent', title, message),
  system: (title: string, message: string) => useNotificationStore.getState().add('system', title, message),
}
