// REST API client for GGUFLoader backend

const BASE_URL = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || 'Request failed')
  }
  return res.json()
}

// Model API
export const modelApi = {
  info: () => request<any>('/model/info'),
  load: (path: string, useGpu = false, nCtx = 32768) =>
    request<any>('/model/load', {
      method: 'POST',
      body: JSON.stringify({ path, use_gpu: useGpu, n_ctx: nCtx, n_gpu_layers: -1 }),
    }),
  unload: () => request<any>('/model/unload', { method: 'DELETE' }),
  estimate: (path: string) => request<any>(`/model/estimate?path=${encodeURIComponent(path)}`),
}

// Chat API
export const chatApi = {
  send: (message: string, options?: { session_id?: string; system_prompt?: string }) =>
    request<any>('/chat/send', {
      method: 'POST',
      body: JSON.stringify({ message, ...options }),
    }),
  health: () => request<any>('/chat/health'),
}

// Session API
export const sessionApi = {
  list: () => request<any[]>('/sessions'),
  create: (title?: string) =>
    request<any>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  get: (id: string) => request<any>(`/sessions/${id}`),
  delete: (id: string) => request<any>(`/sessions/${id}`, { method: 'DELETE' }),
  fork: (id: string) => request<any>(`/sessions/${id}/fork`, { method: 'POST' }),
  search: (query: string) => request<any[]>(`/sessions/search/${encodeURIComponent(query)}`),
  export: (id: string, format: 'json' | 'markdown' | 'html' = 'json') =>
    request<any>(`/sessions/${id}/export?format=${format}`),
}

// Agent API
export const agentApi = {
  status: () => request<any>('/agent/status'),
  start: (preset = 'standard') =>
    request<any>('/agent/start', {
      method: 'POST',
      body: JSON.stringify({ preset }),
    }),
  stop: () => request<any>('/agent/stop', { method: 'POST' }),
  approve: (callId: string, approved: boolean) =>
    request<any>('/agent/approve', {
      method: 'POST',
      body: JSON.stringify({ call_id: callId, approved }),
    }),
  setPreset: (preset: string) =>
    request<any>(`/agent/preset/${preset}`, { method: 'POST' }),
}

// Files API
export const filesApi = {
  tree: (path?: string) => request<any[]>(`/files/tree${path ? `?path=${encodeURIComponent(path)}` : ''}`),
  content: (path: string) => request<any>(`/files/content?path=${encodeURIComponent(path)}`),
  write: (path: string, content: string) =>
    request<any>('/files/content', {
      method: 'PUT',
      body: JSON.stringify({ path, content }),
    }),
  search: (q: string) => request<any[]>(`/files/search?q=${encodeURIComponent(q)}`),
}

// GPU API
export const gpuApi = {
  status: () => request<any>('/gpu/status'),
  install: () => request<any>('/gpu/install', { method: 'POST' }),
}

// Health check
export const healthApi = {
  check: () => request<any>('/health'),
}

// MCP API
export const mcpApi = {
  listServers: () => request<any[]>('/mcp/servers'),
  addServer: (name: string, command: string, args: string[] = []) =>
    request<any>('/mcp/servers', { method: 'POST', body: JSON.stringify({ name, command, args }) }),
  removeServer: (name: string) => request<any>(`/mcp/servers/${name}`, { method: 'DELETE' }),
  connect: (name: string) => request<any>(`/mcp/servers/${name}/connect`, { method: 'POST' }),
  disconnect: (name: string) => request<any>(`/mcp/servers/${name}/disconnect`, { method: 'POST' }),
  listTools: () => request<any[]>('/mcp/tools'),
}

// Tools API
export const toolsApi = {
  list: () => request<any[]>('/tools'),
  stats: () => request<any>('/tools/stats'),
}

// Workflows API
export const workflowsApi = {
  list: () => request<any[]>('/workflows'),
  create: (name: string, description: string = '') =>
    request<any>('/workflows', { method: 'POST', body: JSON.stringify({ name, description }) }),
  templates: () => request<any[]>('/workflows/templates'),
  run: (id: string) => request<any>(`/workflows/${id}/run`, { method: 'POST' }),
}

// Plugins API
export const pluginsApi = {
  list: () => request<any[]>('/plugins'),
  stats: () => request<any>('/plugins/stats'),
  enable: (name: string) => request<any>(`/plugins/${name}/enable`, { method: 'POST' }),
  disable: (name: string) => request<any>(`/plugins/${name}/disable`, { method: 'POST' }),
}
// File Render API
export const fileRenderApi = {
  render: (path: string, search: string = '') =>
    request<any>(`/files/render?path=${encodeURIComponent(path)}&search=${encodeURIComponent(search)}`),
}
