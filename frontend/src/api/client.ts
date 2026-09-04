// REST API client for GGUFLoader backend

import type { AppInfo } from './types'

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
  /** Auto contract: null fields let the router decide. */
  load: (path: string, useGpu: boolean | null = null, nCtx: number | null = null, nGpuLayers: number | null = null, role = 'chat') =>
    request<any>('/model/load', {
      method: 'POST',
      body: JSON.stringify({ path, use_gpu: useGpu, n_ctx: nCtx, n_gpu_layers: nGpuLayers, role }),
    }),
  /** Router plan for a path (optional n_ctx override recomputes fits). */
  plan: (path: string, nCtx?: number | null) =>
    request<any>(`/model/router/plan?path=${encodeURIComponent(path)}${nCtx != null ? `&n_ctx=${nCtx}` : ''}`),
  unload: () => request<any>('/model/unload', { method: 'DELETE' }),
  /** Download the pinned Gemma 4 12B Q4_K_M GGUF into the models folder (background). */
  downloadPinned: () => request<any>('/model/download', { method: 'POST' }),
  downloadStatus: () => request<any>('/model/download/status'),
  estimate: (path: string) => request<any>(`/model/estimate?path=${encodeURIComponent(path)}`),
  /** Deep profile (arch/quant/size) used for pinned-target compatibility checks. */
  inspect: (path: string) => request<any>(`/model/router/inspect?path=${encodeURIComponent(path)}`),
  catalog: (directory?: string, recursive = true) =>
    request<any>(`/model/catalog${directory ? `?directory=${encodeURIComponent(directory)}&recursive=${recursive}` : ''}`),
}

// Chat API
export const chatApi = {
  send: (message: string, options?: { session_id?: string; system_prompt?: string }) =>
    request<any>('/chat/send', {
      method: 'POST',
      body: JSON.stringify({ message, ...options }),
    }),
  health: () => request<any>('/chat/health'),
  dashboard: () => request<any>('/chat/dashboard'),

  /** Stream chat via SSE. Returns an async iterator of tokens. */
  stream: async function* (
    message: string,
    opts?: { system_prompt?: string; temperature?: number; max_tokens?: number },
  ): AsyncGenerator<{ type: 'token' | 'done' | 'error'; data: any }> {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, ...opts }),
    })
    if (!res.ok) throw new Error(`Stream error: ${res.status}`)
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // Parse SSE events
      const events = buffer.split('\n\n')
      buffer = events.pop()! // keep incomplete chunk

      for (const event of events) {
        const lines = event.split('\n')
        let eventType = ''
        let dataStr = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7)
          if (line.startsWith('data: ')) dataStr = line.slice(6)
        }
        if (eventType && dataStr) {
          try {
            yield { type: eventType as any, data: JSON.parse(dataStr) }
          } catch {}
        }
      }
    }
  },
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
  appendMessage: (id: string, role: string, content: string) =>
    request<any>(`/sessions/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify({ role, content }),
    }),
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
  presets: () => request<any[]>('/agent/presets'),
  setPreset: (preset: string) =>
    request<any>(`/agent/preset/${preset}`, { method: 'POST' }),
  sessions: () => request<any[]>('/agent/sessions'),
  replays: () => request<any[]>('/agent/replays'),
  exports: () => request<any[]>('/agent/exports'),
  health: () => request<any>('/agent/health'),

  // Profiling
  profileHistory: (limit = 10) => request<any[]>(`/agent/profile/history?limit=${limit}`),
  profileSteps: (limit = 1) => request<any[]>(`/agent/profile/steps?limit=${limit}`),
  profileBottlenecks: () => request<any>('/agent/profile/bottlenecks'),
  profileThroughput: () => request<any[]>('/agent/profile/throughput'),

  // MCP
  mcpServers: () => request<any[]>('/agent/mcp/servers'),
  mcpTools: () => request<any[]>('/agent/mcp/tools'),

  // Model hot-swap
  modelStatus: () => request<any>('/agent/model/status'),
  modelSwitch: (path: string, opts?: { n_ctx?: number; n_gpu_layers?: number; fallback?: boolean; fallback_chain?: string[] }) =>
    request<any>('/agent/model/switch', {
      method: 'POST',
      body: JSON.stringify({ path, ...opts }),
    }),
  modelUnload: () => request<any>('/agent/model/unload', { method: 'POST' }),
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

// Templates API
export const templatesApi = {
  list: (category?: string) => request<any[]>(`/templates${category ? `?category=${category}` : ''}`),
  categories: () => request<any[]>('/templates/categories'),
  search: (q: string) => request<any[]>(`/templates/search?q=${encodeURIComponent(q)}`),
  get: (id: string) => request<any>(`/templates/${id}`),
  create: (data: { name: string; description: string; template: string; variables: string[]; category: string; tags: string[] }) =>
    request<any>('/templates', { method: 'POST', body: JSON.stringify(data) }),
  render: (id: string, variables: Record<string, string>) =>
    request<any>('/templates/render', { method: 'POST', body: JSON.stringify({ template_id: id, variables }) }),
  compose: (ids: string[], _variables: Record<string, string> = {}) =>
    request<any>('/templates/compose', { method: 'POST', body: JSON.stringify(ids), headers: { 'Content-Type': 'application/json' } }),
  delete: (id: string) => request<any>(`/templates/${id}`, { method: 'DELETE' }),
}

// Branching API
export const branchingApi = {
  branches: (sessionId: string) => request<any[]>(`/branching/${sessionId}/branches`),
  timeline: (sessionId: string) => request<any[]>(`/branching/${sessionId}/timeline`),
  fork: (sessionId: string, branchId: string, messageIndex: number, name?: string) =>
    request<any>(`/branching/${sessionId}/fork`, {
      method: 'POST', body: JSON.stringify({ session_id: sessionId, branch_id: branchId, message_index: messageIndex, name: name || '' }),
    }),
  merge: (sessionId: string, source: string, target: string, strategy = 'append') =>
    request<any>(`/branching/${sessionId}/merge`, {
      method: 'POST', body: JSON.stringify({ session_id: sessionId, source_branch: source, target_branch: target, strategy }),
    }),
  diff: (sessionId: string, branchA: string, branchB: string) =>
    request<any>(`/branching/${sessionId}/diff`, {
      method: 'POST', body: JSON.stringify({ session_id: sessionId, branch_a: branchA, branch_b: branchB }),
    }),
  messages: (sessionId: string, branchId: string) => request<any[]>(`/branching/${sessionId}/messages/${branchId}`),
}

// Diff API
export const diffApi = {
  compute: (oldText: string, newText: string, filename?: string) =>
    request<any>('/branching/diff/compute', {
      method: 'POST', body: JSON.stringify({ old_text: oldText, new_text: newText, filename: filename || '' }),
    }),
  sideBySide: (oldText: string, newText: string, filename?: string) =>
    request<any>('/branching/diff/side-by-side', {
      method: 'POST', body: JSON.stringify({ old_text: oldText, new_text: newText, filename: filename || '' }),
    }),
  fromResults: (toolResults: any[]) =>
    request<any>('/branching/diff/from-results', {
      method: 'POST', body: JSON.stringify({ tool_results: toolResults }),
    }),
}

// Health check
export const healthApi = {
  check: () => request<any>('/health'),
}

// App identity (version banner + first-launch compatibility)
export const appApi = {
  info: () => request<AppInfo>('/app/info'),
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

// Workflows API (builder routes under /api/agent/workflows)
export const workflowsApi = {
  list: () => request<any[]>('/agent/workflows'),
  templates: () => request<any[]>('/agent/workflows/templates'),
  create: (name: string, description: string = '') =>
    request<any>('/agent/workflows', {
      method: 'POST', body: JSON.stringify({ name, description }),
    }),
  duplicate: (id: string) =>
    request<any>(`/agent/workflows/${id}/duplicate`, { method: 'POST' }),
  delete: (id: string) =>
    request<any>(`/agent/workflows/${id}`, { method: 'DELETE' }),
  validate: (id: string) =>
    request<any>(`/agent/workflows/${id}/validate`, { method: 'POST' }),
  dryRun: (id: string) =>
    request<any>(`/agent/workflows/${id}/dry-run`, { method: 'POST' }),
  fromTemplate: (id: string, templateId: string) =>
    request<any>(`/agent/workflows/${id}/from-template`, {
      method: 'POST', body: JSON.stringify({ template_id: templateId }),
    }),
  run: (id: string) => request<any>(`/workflows/${id}/run`, { method: 'POST' }),
  get: (id: string) => request<any>(`/agent/workflows/${id}`),
  updateSteps: (id: string, steps: any[]) =>
    request<any>(`/agent/workflows/${id}/steps`, {
      method: 'PUT', body: JSON.stringify(steps),
    }),
}

// Collaboration API
export const collabApi = {
  active: () => request<any[]>('/agent/collab/active'),
  session: (id: string) => request<any>(`/agent/collab/session/${id}`),
  join: (sessionId: string, name: string) =>
    request<any>('/agent/collab/join', {
      method: 'POST', body: JSON.stringify({ session_id: sessionId, name }),
    }),
  leave: (sessionId: string, userId: string) =>
    request<any>('/agent/collab/leave', {
      method: 'POST', body: JSON.stringify({ session_id: sessionId, user_id: userId }),
    }),
}

// Benchmark API
export const benchmarkApi = {
  prompts: () => request<any[]>('/benchmark/prompts'),
  history: (limit = 20) => request<any[]>(`/benchmark/history?limit=${limit}`),
  reports: () => request<any[]>('/benchmark/reports'),
  report: (id: string) => request<any>(`/benchmark/reports/${id}`),
  compare: (ids: string[]) =>
    request<any>('/benchmark/compare', {
      method: 'POST', body: JSON.stringify({ report_ids: ids }),
    }),
  run: (modelName: string, modelPath: string) =>
    request<any>('/benchmark/run', {
      method: 'POST', body: JSON.stringify({ model_name: modelName, model_path: modelPath }),
    }),
}

// Workspace API
export const workspaceApi = {
  list: () => request<any[]>('/workspaces'),
  active: () => request<any>('/workspaces/active'),
  create: (name: string) =>
    request<any>('/workspaces', {
      method: 'POST', body: JSON.stringify({ name }),
    }),
  switch: (id: string) =>
    request<any>(`/workspaces/${id}/switch`, { method: 'POST' }),
  rename: (id: string, name: string) =>
    request<any>(`/workspaces/${id}`, {
      method: 'PUT', body: JSON.stringify({ name }),
    }),
  delete: (id: string) =>
    request<any>(`/workspaces/${id}`, { method: 'DELETE' }),
  settings: (id: string) => request<any>(`/workspaces/${id}/settings`),
  updateSettings: (id: string, settings: any) =>
    request<any>(`/workspaces/${id}/settings`, {
      method: 'PUT', body: JSON.stringify(settings),
    }),
}

// Search API
export const searchApi = {
  search: (pattern: string, opts?: { search_type?: string; scope?: string; case_sensitive?: boolean }) =>
    request<any>('/search', {
      method: 'POST', body: JSON.stringify({ pattern, ...opts }),
    }),
  savedQueries: () => request<any[]>('/search/queries'),
  saveQuery: (name: string, pattern: string, searchType: string = 'text') =>
    request<any>('/search/queries', {
      method: 'POST', body: JSON.stringify({ name, pattern, search_type: searchType }),
    }),
  deleteQuery: (id: string) =>
    request<any>(`/search/queries/${id}`, { method: 'DELETE' }),
  history: (limit = 50) => request<any[]>(`/search/history?limit=${limit}`),
  clearHistory: () => request<any>('/search/history', { method: 'DELETE' }),
}

// Plugins API
export const pluginsApi = {
  list: () => request<any[]>('/plugins'),
  stats: () => request<any>('/plugins/stats'),
  catalog: (category?: string) => request<any[]>(`/plugins/catalog${category ? `?category=${category}` : ''}`),
  categories: () => request<any[]>('/plugins/catalog/categories'),
  enable: (name: string) => request<any>(`/plugins/${name}/enable`, { method: 'POST' }),
  disable: (name: string) => request<any>(`/plugins/${name}/disable`, { method: 'POST' }),
}
// File Render API
export const fileRenderApi = {
  render: (path: string, search: string = '') =>
    request<any>(`/files/render?path=${encodeURIComponent(path)}&search=${encodeURIComponent(search)}`),
}

// WASM Sandbox API
export const sandboxApi = {
  status: () => request<any>('/sandbox/status'),
  plugins: () => request<any[]>('/sandbox/plugins'),
  instances: () => request<any[]>('/sandbox/instances'),
  load: (wasmPath: string, manifestPath?: string, opts?: { max_memory_mb?: number; max_cpu_time_s?: number }) =>
    request<any>('/sandbox/load', {
      method: 'POST', body: JSON.stringify({ wasm_path: wasmPath, manifest_path: manifestPath, ...opts }),
    }),
  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<any>('/sandbox/upload', { method: 'POST', body: formData })
  },
  unload: (instanceId: string) =>
    request<any>(`/sandbox/instances/${instanceId}`, { method: 'DELETE' }),
  call: (instanceId: string, fn: string = 'process', input: any = {}, timeoutMs?: number) =>
    request<any>(`/sandbox/instances/${instanceId}/call`, {
      method: 'POST', body: JSON.stringify({ function: fn, input_data: input, timeout_ms: timeoutMs }),
    }),
  metrics: (instanceId: string) => request<any>(`/sandbox/instances/${instanceId}/metrics`),
  deleteFile: (filename: string) =>
    request<any>(`/sandbox/plugins/${filename}`, { method: 'DELETE' }),
}
