// Model types
export interface ModelInfo {
  loaded: boolean
  path?: string
  filename?: string
  family?: string
  architecture?: string
  quantization?: string
  parameters?: string
  context_length?: number
  gpu: boolean
}

export interface LoadRequest {
  path: string
  use_gpu: boolean
  n_ctx: number
  n_gpu_layers: number
}

// Session types
export interface SessionInfo {
  id: string
  title?: string
  created: string
  updated: string
  mode: string
  message_count: number
}

export interface Message {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  ts?: string
  thinking_ms?: number
}

// Agent types
export interface AgentStatus {
  running: boolean
  preset: string
  model_loaded: boolean
  workspace?: string
}

// File types
export interface FileNode {
  name: string
  path: string
  is_dir: boolean
  children?: FileNode[]
}

export interface FileContent {
  path: string
  content: string
  size: number
}

// WebSocket events
export interface WSEvent {
  type: string
  [key: string]: any
}

export interface TokenEvent extends WSEvent {
  type: 'token'
  content: string
  message_id: string
}

export interface ToolCallEvent extends WSEvent {
  type: 'tool_call'
  name: string
  args: Record<string, any>
  call_id: string
}

export interface ApprovalEvent extends WSEvent {
  type: 'approval_needed'
  call_id: string
  tool: string
  risk: string
}

export interface MessageCompleteEvent extends WSEvent {
  type: 'message_complete'
  message_id: string
  content: string
  tokens_used: number
  duration_ms: number
}
