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

export interface PlanStep {
  step: number
  description: string
  status: 'pending' | 'running' | 'done' | 'failed'
  result?: string
}

export interface PlanState {
  phase: 'idle' | 'goal' | 'plan' | 'execute' | 'verify' | 'continue' | 'finish'
  goal: string
  plan: PlanStep[]
  planStep: { current: number; total: number; description: string } | null
  phaseLog: string[]
}

interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  currentStreamingId: string | null
  streamingText: string
  reasoningBlocks: string[]
  pendingApprovals: ToolApprovalRequest[]
  plan: PlanState
  isAgentMode: boolean
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
  updatePlan: (phase: string, plan?: PlanStep[], planStep?: PlanState['planStep'], goal?: string) => void
  resetPlan: () => void
  setAgentMode: (v: boolean) => void
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
  plan: { phase: 'idle', goal: '', plan: [], planStep: null, phaseLog: [] },
  isAgentMode: false,

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

  updatePlan: (phase, plan, planStep, goal) => set((s) => ({
    plan: {
      ...s.plan,
      phase: (phase as PlanState['phase']) || s.plan.phase,
      ...(plan !== undefined && { plan }),
      ...(planStep !== undefined && { planStep }),
      ...(goal && { goal }),
    },
  })),

  resetPlan: () => set({ plan: { phase: 'idle', goal: '', plan: [], planStep: null, phaseLog: [] } }),

  setAgentMode: (v) => set({ isAgentMode: v }),

  clearMessages: () => set({ messages: [], isStreaming: false, currentStreamingId: null, streamingText: '', reasoningBlocks: [], plan: { phase: 'idle', goal: '', plan: [], planStep: null, phaseLog: [] } }),

  sendMessage: async (text: string) => {
    const store = get()
    store.addMessage({ id: `user_${Date.now()}`, role: 'user', content: text, timestamp: Date.now() })

    // Load sampling params from localStorage
    let sampling = { temperature: 0.7, max_tokens: 4096 }
    let systemPrompt = ''
    try {
      const saved = localStorage.getItem('ggufloader_settings')
      if (saved) {
        const s = JSON.parse(saved)
        if (s.sampling) sampling = { ...sampling, ...s.sampling }
        if (s.systemPrompt) systemPrompt = s.systemPrompt
      }
    } catch {}

    // Try WebSocket first, fallback to REST
    if (ws && ws.readyState === WebSocket.OPEN) {
      const msgId = store.startStreaming()
      store.addMessage({ id: msgId, role: 'assistant', content: '', timestamp: Date.now() })
      const isAgent = get().isAgentMode
      ws.send(JSON.stringify({
        type: isAgent ? 'agent_start' : 'chat_message',
        message: text,
        temperature: sampling.temperature,
        max_tokens: sampling.max_tokens,
        system_prompt: systemPrompt || undefined,
      }))
    } else {
      const msgId = store.startStreaming()
      store.addMessage({ id: msgId, role: 'assistant', content: '', timestamp: Date.now() })
      try {
        const res = await fetch('/api/chat/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, system_prompt: systemPrompt || undefined }),
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
          // Add tool call to current streaming message
          if (store.currentStreamingId) {
            const msgs = useChatStore.getState().messages
            const current = msgs.find(m => m.id === store.currentStreamingId)
            if (current) {
              current.toolCalls = [...(current.toolCalls || []), {
                name: data.name,
                args: data.args || {},
                status: 'running' as const,
                approvalId: data.call_id,
              }]
              useChatStore.setState({ messages: [...msgs] })
            }
          }
          break
        case 'tool_result':
          if (store.currentStreamingId) {
            const msgs = useChatStore.getState().messages
            const current = msgs.find(m => m.id === store.currentStreamingId)
            if (current && current.toolCalls) {
              const tc = current.toolCalls.find(t => t.approvalId === data.call_id || t.name === data.tool)
              if (tc) {
                tc.status = data.success ? 'completed' : 'failed'
                tc.result = data.result || data.error
                useChatStore.setState({ messages: [...msgs] })
              }
            }
          }
          break
        case 'agent_phase':
          // Handle structured phase events from agent engine
          useChatStore.getState().updatePlan(
            data.phase || 'idle',
            undefined,
            data.plan_step || undefined,
          )
          // Append phase status as reasoning block
          if (data.status) {
            useChatStore.getState().addReasoningBlock(data.status)
          }
          break
        case 'agent_plan_update':
          // Real-time plan step status updates (running -> done/failed)
          useChatStore.getState().updatePlan(
            data.phase || 'idle',
            data.plan || undefined,
            data.step ? { current: data.step, total: (data.plan || []).length, description: '' } : undefined,
          )
          break
        case 'agent_complete':
          // Final plan + phase log from agent run
          useChatStore.getState().updatePlan(
            'idle',
            data.plan || [],
            null,
          )
          useChatStore.setState((s) => ({
            plan: { ...s.plan, phaseLog: data.phase_log || [] },
          }))
          break
        case 'message_complete':
          // Update streaming message with final content + plan
          if (store.currentStreamingId) {
            const msgs = useChatStore.getState().messages
            const current = msgs.find(m => m.id === store.currentStreamingId)
            if (current) {
              current.content = data.content || current.content
              useChatStore.setState({ messages: [...msgs] })
            }
          }
          if (data.plan) {
            useChatStore.getState().updatePlan('idle', data.plan)
          }
          store.stopStreaming()
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
