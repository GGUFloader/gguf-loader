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
