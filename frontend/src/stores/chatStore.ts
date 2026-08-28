import { create } from 'zustand'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  thinking?: string
  toolCalls?: ToolCall[]
}

export interface ToolCall {
  name: string
  args: Record<string, any>
  status: 'running' | 'completed' | 'failed' | 'pending_approval'
  result?: string
  approvalId?: string
}

export interface ToolApprovalRequest {
  id: string
  tool: string
  args: Record<string, any>
}

interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  currentStreamingId: string | null
  streamingText: string
  reasoningBlocks: string[]
  pendingApprovals: ToolApprovalRequest[]
  addMessage: (msg: ChatMessage) => void
  appendToMessage: (id: string, content: string) => void
  setThinking: (id: string, thinking: string) => void
  startStreaming: () => string
  stopStreaming: () => void
  setStreamingText: (text: string) => void
  appendStreamingText: (token: string) => void
  addReasoningBlock: (content: string) => void
  addPendingApproval: (req: ToolApprovalRequest) => void
  removePendingApproval: (id: string) => void
  clearMessages: () => void
  sendMessage: (text: string) => Promise<void>
}

let ws: WebSocket | null = null

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  currentStreamingId: null,
  streamingText: '',
  reasoningBlocks: [],
  pendingApprovals: [],

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  appendToMessage: (id, content) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + content } : m
      ),
    })),

  setThinking: (id, thinking) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, thinking } : m
      ),
    })),

  startStreaming: () => {
    const id = `msg_${Date.now()}`
    set({ isStreaming: true, currentStreamingId: id, streamingText: '', reasoningBlocks: [] })
    return id
  },

  stopStreaming: () => {
    const { streamingText, currentStreamingId } = get()
    if (currentStreamingId && streamingText) {
      // Move streaming text to a permanent message
      get().appendToMessage(currentStreamingId, streamingText)
    }
    set({ isStreaming: false, currentStreamingId: null, streamingText: '' })
  },

  setStreamingText: (text) => set({ streamingText: text }),

  appendStreamingText: (token) => set((s) => ({ streamingText: s.streamingText + token })),

  addReasoningBlock: (content) => set((s) => ({ reasoningBlocks: [...s.reasoningBlocks, content] })),

  addPendingApproval: (req) => set((s) => ({ pendingApprovals: [...s.pendingApprovals, req] })),

  removePendingApproval: (id) => set((s) => ({
    pendingApprovals: s.pendingApprovals.filter((p) => p.id !== id),
  })),

  clearMessages: () => set({ messages: [], isStreaming: false, currentStreamingId: null, streamingText: '', reasoningBlocks: [] }),

  sendMessage: async (text: string) => {
    const store = get()
    store.addMessage({ id: `user_${Date.now()}`, role: 'user', content: text, timestamp: Date.now() })

    // Try WebSocket first, fallback to REST
    if (ws && ws.readyState === WebSocket.OPEN) {
      const msgId = store.startStreaming()
      store.addMessage({ id: msgId, role: 'assistant', content: '', timestamp: Date.now() })
      ws.send(JSON.stringify({ type: 'chat_message', message: text }))
    } else {
      const msgId = store.startStreaming()
      store.addMessage({ id: msgId, role: 'assistant', content: '', timestamp: Date.now() })
      try {
        const res = await fetch('/api/chat/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text }),
        })
        const data = await res.json()
        store.appendToMessage(msgId, data.response)
      } catch (e: any) {
        store.appendToMessage(msgId, `Error: ${e.message}`)
      } finally {
        store.stopStreaming()
      }
    }
  },
}))

// WebSocket connection singleton
export function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${protocol}//${window.location.host}/ws`)
  const store = useChatStore.getState()

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      switch (data.type) {
        case 'token':
          store.appendStreamingText(data.token)
          break
        case 'reasoning':
          store.addReasoningBlock(data.content)
          break
        case 'tool_call':
          // TODO: handle tool call display
          break
        case 'tool_result':
          // TODO: handle tool result display
          break
        case 'tool_approval':
          store.addPendingApproval({ id: data.id, tool: data.tool, args: data.args })
          break
        case 'done':
          store.stopStreaming()
          break
        case 'error':
          store.appendToMessage(store.currentStreamingId ?? '', `\nError: ${data.message}`)
          store.stopStreaming()
          break
      }
    } catch {}
  }

  ws.onclose = () => {
    // Reconnect after 2s
    setTimeout(connectWebSocket, 2000)
  }
}
