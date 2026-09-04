import { create } from 'zustand'

/**
 * Coerce a wire payload into display text. Non-string JSON values become JSON
 * (never the literal "[object Object]"), null/undefined become ''.
 */
function toText(v: unknown): string {
  if (typeof v === 'string') return v
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') {
    try {
      return JSON.stringify(v)
    } catch {
      return String(v)
    }
  }
  return String(v)
}

/** Token events must carry strings; anything else is protocol drift — drop it. */
function toTokenText(v: unknown): string {
  return typeof v === 'string' ? v : ''
}

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

export interface ProgressStep {
  id: string
  type: 'announce' | 'tool_call' | 'tool_result' | 'message' | 'error' | 'thinking'
  content: string
  timestamp: number
  toolName?: string
  toolArgs?: Record<string, any>
  toolResult?: string
  success?: boolean
  completedSteps?: number
  active?: boolean
}

export interface AgentMetrics {
  tokenCount: number
  toolCalls: number
  toolSuccesses: number
  durationMs: number
  preset: string
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
  agentMetrics: AgentMetrics
  progressSteps: ProgressStep[]
  currentAnnouncement: string
  activeSessionId: string | null
  setActiveSessionId: (id: string | null) => void
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
  updateAgentMetrics: (partial: Partial<AgentMetrics>) => void
  resetAgentMetrics: () => void
  clearMessages: () => void
  sendMessage: (text: string) => Promise<void>
  // Progress step actions
  addProgressStep: (step: Omit<ProgressStep, 'id' | 'timestamp'>) => void
  setCurrentAnnouncement: (text: string) => void
  updateProgressStep: (id: string, updates: Partial<ProgressStep>) => void
  clearProgressSteps: () => void
}

let ws: WebSocket | null = null

const DEFAULT_METRICS: AgentMetrics = {
  tokenCount: 0,
  toolCalls: 0,
  toolSuccesses: 0,
  durationMs: 0,
  preset: '',
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  currentStreamingId: null,
  streamingText: '',
  reasoningBlocks: [],
  pendingApprovals: [],
  plan: { phase: 'idle', goal: '', plan: [], planStep: null, phaseLog: [] },
  isAgentMode: false,
  agentMetrics: { ...DEFAULT_METRICS },
  progressSteps: [],
  currentAnnouncement: '',
  activeSessionId: null,

  setActiveSessionId: (id) => set({ activeSessionId: id }),

  addMessage: (msg) => {
    set((s) => ({ messages: [...s.messages, msg] }))
    // Auto-save to active session
    const state = get()
    if (state.activeSessionId && (msg.role === 'user' || msg.role === 'assistant') && msg.content) {
      import('../api/client').then(({ sessionApi }) => {
        sessionApi.appendMessage(state.activeSessionId!, msg.role, msg.content).catch(() => {})
      })
    }
  },

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
    set({
      isStreaming: true,
      currentStreamingId: id,
      streamingText: '',
      reasoningBlocks: [],
      agentMetrics: { ...DEFAULT_METRICS },
    })
    return id
  },

  stopStreaming: () => {
    const { streamingText, currentStreamingId } = get()
    if (currentStreamingId && streamingText) {
      get().appendToMessage(currentStreamingId, streamingText)
    }
    set({ isStreaming: false, currentStreamingId: null, streamingText: '' })
  },

  setStreamingText: (text) => set({ streamingText: text }),

  appendStreamingText: (token) => set((s) => {
    const t = toTokenText(token)
    if (!t) return s
    return {
      streamingText: s.streamingText + t,
      agentMetrics: { ...s.agentMetrics, tokenCount: s.agentMetrics.tokenCount + 1 },
    }
  }),

  addReasoningBlock: (content) => set((s) => ({
    reasoningBlocks: [...s.reasoningBlocks, content],
  })),

  addPendingApproval: (req) => set((s) => ({
    pendingApprovals: [...s.pendingApprovals, req],
  })),

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

  updateAgentMetrics: (partial) => set((s) => ({
    agentMetrics: { ...s.agentMetrics, ...partial },
  })),

  resetAgentMetrics: () => set({ agentMetrics: { ...DEFAULT_METRICS } }),

  addProgressStep: (step) => set((s) => ({
    progressSteps: [...s.progressSteps, {
      ...step,
      id: `ps_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      timestamp: Date.now(),
    }],
  })),

  setCurrentAnnouncement: (text) => set({ currentAnnouncement: text }),

  updateProgressStep: (id, updates) => set((s) => ({
    progressSteps: s.progressSteps.map((ps) =>
      ps.id === id ? { ...ps, ...updates } : ps
    ),
  })),

  clearProgressSteps: () => set({ progressSteps: [], currentAnnouncement: '' }),

  clearMessages: () => set({
    messages: [],
    isStreaming: false,
    currentStreamingId: null,
    streamingText: '',
    reasoningBlocks: [],
    plan: { phase: 'idle', goal: '', plan: [], planStep: null, phaseLog: [] },
    agentMetrics: { ...DEFAULT_METRICS },
    progressSteps: [],
    currentAnnouncement: '',
  }),

  sendMessage: async (text: string) => {
    const store = get()
    // Clear progress steps from previous turn
    store.clearProgressSteps()
    store.addMessage({ id: `user_${Date.now()}`, role: 'user', content: text, timestamp: Date.now() })

    // Load settings from localStorage
    let sampling = { temperature: 0.7, max_tokens: 4096 }
    let systemPrompt = ''
    let workspace = '.'
    let preset = 'full_stack'
    try {
      const saved = localStorage.getItem('ggufloader_settings')
      if (saved) {
        const s = JSON.parse(saved)
        if (s.sampling) sampling = { ...sampling, ...s.sampling }
        if (s.systemPrompt) systemPrompt = s.systemPrompt
        if (s.workspace) workspace = s.workspace
        if (s.preset) preset = s.preset
      }
    } catch {}

    // Get current model path from model store
    let modelPath: string | undefined
    try {
      const { useModelStore } = await import('./modelStore')
      const modelInfo = useModelStore.getState().info
      if (modelInfo?.path) modelPath = modelInfo.path
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
        // Agent-specific fields
        ...(isAgent ? {
          workspace,
          preset,
          model_path: modelPath,
        } : {}),
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
          store.appendStreamingText(toTokenText(data.token))
          break
        case 'reasoning': {
          // Live planner deltas: append into the latest thinking step so the
          // streamed plan reasoning accumulates in ONE sidebar card instead
          // of creating a new card per chunk.
          const st = useChatStore.getState()
          const lastThinking = [...st.progressSteps].reverse().find(
            (s) => s.type === 'thinking'
          )
          const content = toText(data.content)
          if (lastThinking) {
            useChatStore.getState().updateProgressStep(lastThinking.id, {
              content: lastThinking.content + content,
            })
          } else {
            useChatStore.getState().addProgressStep({
              type: 'thinking',
              content,
            })
          }
          break
        }
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
                tc.result = toText(data.result) || toText(data.error)
                useChatStore.setState({ messages: [...msgs] })
              }
            }
          }
          // Update agent metrics
          useChatStore.getState().updateAgentMetrics({
            toolCalls: useChatStore.getState().agentMetrics.toolCalls + 1,
            toolSuccesses: useChatStore.getState().agentMetrics.toolSuccesses + (data.success ? 1 : 0),
          })
          break
        case 'progress_announce':
          // Agent announces what it's about to do.
          // If there's already a pending announcement, commit it first.
          {
            const prev = useChatStore.getState().currentAnnouncement
            if (prev) {
              useChatStore.getState().addProgressStep({
                type: 'announce',
                content: prev,
              })
            }
          }
          useChatStore.getState().setCurrentAnnouncement(data.content)
          break
        case 'progress_tool_call':
          // Agent is executing a tool
          useChatStore.getState().addProgressStep({
            type: 'tool_call',
            content: toText(data.content) || toText(data.name),
            toolName: data.name,
            toolArgs: data.args,
            active: true,
          })
          break
        case 'progress_tool_result':
          // Tool completed — mark the last active tool_call as done
          {
            const state = useChatStore.getState()
            const lastActive = [...state.progressSteps].reverse().find(
              s => s.type === 'tool_call' && s.active
            )
            if (lastActive) {
              useChatStore.getState().updateProgressStep(lastActive.id, {
                active: false,
                success: data.success,
              })
            }
            useChatStore.getState().addProgressStep({
              type: 'tool_result',
              content: toText(data.result) || toText(data.error) || 'Done',
              toolName: data.tool,
              toolResult: toText(data.result) || toText(data.error),
              success: data.success,
            })
          }
          // Commit announcement when first tool starts
          {
            const announcement = useChatStore.getState().currentAnnouncement
            if (announcement) {
              useChatStore.getState().addProgressStep({
                type: 'announce',
                content: announcement,
              })
              useChatStore.getState().setCurrentAnnouncement('')
            }
          }
          break
        case 'progress_step_complete':
          // A high-level step is done
          useChatStore.getState().addProgressStep({
            type: 'message',
            content: toText(data.content),
          })
          break
        case 'agent_phase':
          useChatStore.getState().updatePlan(
            data.phase || 'idle',
            undefined,
            data.plan_step || undefined,
          )
          // Add thinking content as progress steps in the timeline
          // instead of separate reasoning blocks (which pile up at top)
          const statusText = toText(data.status)
          if (statusText) {
            const s = statusText.trim()
            if (s.startsWith('💡') || s.startsWith('🤔') || s.startsWith('💭')) {
              const clean = s.replace(/^[🤔💡💭]\s*/, '')
              if (clean) {
                useChatStore.getState().addProgressStep({
                  type: 'thinking',
                  content: clean,
                })
              }
            }
          }
          if (data.preset) {
            useChatStore.getState().updateAgentMetrics({ preset: data.preset })
          }
          break
        case 'agent_plan_update':
          useChatStore.getState().updatePlan(
            data.phase || 'idle',
            data.plan || undefined,
            data.step ? { current: data.step, total: (data.plan || []).length, description: '' } : undefined,
          )
          break
        case 'agent_complete':
          useChatStore.getState().updatePlan('idle', data.plan || [], null)
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
              current.content = toText(data.content) || current.content
              useChatStore.setState({ messages: [...msgs] })
            }
          }
          if (data.plan) {
            useChatStore.getState().updatePlan('idle', data.plan)
          }
          // Commit any remaining announcement as final message
          {
            const announcement = useChatStore.getState().currentAnnouncement
            if (announcement) {
              useChatStore.getState().addProgressStep({
                type: 'announce',
                content: announcement,
              })
              useChatStore.getState().setCurrentAnnouncement('')
            }
          }
          // Update duration metric
          if (data.duration_ms) {
            useChatStore.getState().updateAgentMetrics({ durationMs: data.duration_ms })
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
          store.appendToMessage(store.currentStreamingId ?? '', `\nError: ${toText(data.message)}`)
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
