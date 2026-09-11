import { useState, useEffect } from 'react'
import {
  X, Bot, Palette, Keyboard, Cpu, Sliders,
  FolderOpen, RefreshCw, Zap, Trash2, Eye, EyeOff, Globe, Cloud,
  Search, FileText, Bug, Rocket, Puzzle,
} from 'lucide-react'
import { useUIStore } from '../../stores/uiStore'
import { gpuApi, agentApi } from '../../api/client'
import { usePluginRegistry } from '../../stores/pluginRegistry'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { ThemeSwitcher } from '../ui/ThemeSwitcher'

interface Props {
  onClose: () => void
}

const TABS = [
  { id: 'model', label: 'Model', icon: Cpu },
  { id: 'providers', label: 'Providers', icon: Cloud },
  { id: 'agent', label: 'Agent', icon: Bot },
  { id: 'hardware', label: 'Hardware', icon: Zap },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'keyboard', label: 'Keyboard', icon: Keyboard },
  { id: 'plugins', label: 'Plugins', icon: Puzzle },
]

const SHORTCUTS = [
  { keys: 'Enter', action: 'Send message' },
  { keys: 'Shift+Enter', action: 'New line' },
  { keys: '@', action: 'Mention file' },
  { keys: 'Ctrl+M', action: 'Toggle agent mode' },
  { keys: 'Esc', action: 'Stop generation' },
  { keys: 'Ctrl+/', action: 'Keyboard shortcuts' },
  { keys: 'Ctrl+K', action: 'Focus search' },
  { keys: 'Ctrl+N', action: 'New chat' },
  { keys: 'Ctrl+B', action: 'Toggle left panel' },
  { keys: 'Ctrl+\\', action: 'Toggle right panel' },
  { keys: 'Ctrl+L', action: 'Clear terminal' },
]

const DEFAULT_SAMPLING = {
  temperature: 0.7,
  top_p: 0.9,
  min_p: 0.05,
  top_k: 40,
  repeat_penalty: 1.1,
  max_tokens: 4096,
}

export function SettingsDialog({ onClose }: Props) {
  const [activeTab, setActiveTab] = useState('model')
  useUIStore()

  // Model settings
  const [gpuLayers, setGpuLayers] = useState(-1)
  const [ctxLength, setCtxLength] = useState(0) // 0 = Auto (router decides)
  const [autoLoad, setAutoLoad] = useState(false)

  // Sampling params
  const [sampling, setSampling] = useState(DEFAULT_SAMPLING)
  const isGreedy = sampling.temperature === 0

  // Agent settings
  const [preset, setPreset] = useState('standard')
  const [maxToolCalls, setMaxToolCalls] = useState(20)
  const [requireApproval, setRequireApproval] = useState(true)
  const [autoCommit, setAutoCommit] = useState(false)
  const [systemPrompt, setSystemPrompt] = useState('')
  const [ragEnabled, setRagEnabled] = useState(false)
  const [ragFolder, setRagFolder] = useState('')
  const workspace = useWorkspaceStore((s) => s.workspace)
  const setWorkspace = useWorkspaceStore((s) => s.setWorkspace)

  // Hardware
  const [gpuStatus, setGpuStatus] = useState<any>(null)
  const [gpuInstalling, setGpuInstalling] = useState(false)
  const [gpuLoading, setGpuLoading] = useState(true)

  // Appearance
  const [fontSize, setFontSize] = useState(14)
  const [compactMode, setCompactMode] = useState(false)
  const [accentColor, setAccentColor] = useState('#f59e0b')

  // Provider catalog
  const [providers, setProviders] = useState<Record<string, { apiKey: string; endpoint: string; enabled: boolean }>>({
    anthropic: { apiKey: '', endpoint: 'https://api.anthropic.com', enabled: false },
    openai: { apiKey: '', endpoint: 'https://api.openai.com/v1', enabled: false },
    openrouter: { apiKey: '', endpoint: 'https://openrouter.ai/api/v1', enabled: false },
    custom: { apiKey: '', endpoint: '', enabled: false },
  })
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})

  // Load GPU status on mount
  useEffect(() => {
    gpuApi.status().then(setGpuStatus).catch(() => {}).finally(() => setGpuLoading(false))
  }, [])

  // Load saved settings from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('ggufloader_settings')
      if (saved) {
        const s = JSON.parse(saved)
        if (s.sampling) setSampling({ ...DEFAULT_SAMPLING, ...s.sampling })
        if (s.gpuLayers !== undefined) setGpuLayers(s.gpuLayers)
        if (s.ctxLength) setCtxLength(s.ctxLength)
        if (s.systemPrompt) setSystemPrompt(s.systemPrompt)
        if (s.workspace) setWorkspace(s.workspace)
        if (s.preset) setPreset(s.preset)
        if (s.maxToolCalls) setMaxToolCalls(s.maxToolCalls)
        if (s.requireApproval !== undefined) setRequireApproval(s.requireApproval)
        if (s.ragEnabled !== undefined) setRagEnabled(s.ragEnabled)
        if (s.ragFolder) setRagFolder(s.ragFolder)
        if (s.fontSize) setFontSize(s.fontSize)
        if (s.compactMode !== undefined) setCompactMode(s.compactMode)
        if (s.accentColor) setAccentColor(s.accentColor)
        if (s.providers) setProviders(s.providers)
      }
    } catch {}
  }, [])

  function saveSettings() {
    const settings = {
      sampling, gpuLayers, ctxLength, systemPrompt, workspace,
      preset, maxToolCalls, requireApproval, autoCommit,
      ragEnabled, ragFolder, fontSize, compactMode, accentColor,
      providers,
    }
    localStorage.setItem('ggufloader_settings', JSON.stringify(settings))
  }

  function updateSampling(key: string, value: number) {
    setSampling(prev => ({ ...prev, [key]: value }))
    setTimeout(saveSettings, 100)
  }

  async function handleGpuInstall() {
    setGpuInstalling(true)
    try {
      await gpuApi.install()
      const status = await gpuApi.status()
      setGpuStatus(status)
    } catch {}
    setGpuInstalling(false)
  }

  function handleBrowseWorkspace() {
    if ((window as any).electronAPI?.openFolderDialog) {
      (window as any).electronAPI.openFolderDialog().then((path: string | null) => {      if (path) { setWorkspace(path) }
    })
    } else {
      const path = prompt('Enter workspace folder path:')
      if (path) { setWorkspace(path) }
    }
  }

  function handleBrowseRag() {
    if ((window as any).electronAPI?.openFolderDialog) {
      (window as any).electronAPI.openFolderDialog().then((path: string | null) => {
        if (path) { setRagFolder(path); setTimeout(saveSettings, 100) }
      })
    } else {
      const path = prompt('Enter RAG documents folder path:')
      if (path) { setRagFolder(path); setTimeout(saveSettings, 100) }
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface border border-border rounded-xl shadow-2xl w-[720px] max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Sliders size={18} className="text-accent" />
            <h2 className="text-base font-semibold text-text">Settings</h2>
          </div>
          <button onClick={onClose} className="p-1.5 text-text-muted hover:text-text rounded-lg hover:bg-elevated transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Tab sidebar */}
          <div className="w-40 border-r border-border py-2 space-y-0.5">
            {TABS.map((tab) => {
              const Icon = tab.icon
              return (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm transition-colors ${activeTab === tab.id ? 'bg-accent/10 text-accent font-medium' : 'text-text-sec hover:bg-elevated'}`}>
                  <Icon size={15} />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {/* === MODEL TAB === */}
            {activeTab === 'model' && (
              <div className="space-y-6">
                <Section title="Model Loading">
                  <Field label="GPU Layers">
                    <div className="flex items-center gap-2">
                      <input type="number" value={gpuLayers} onChange={(e) => { setGpuLayers(Number(e.target.value)); setTimeout(saveSettings, 100) }}
                        className="w-24 bg-elevated border border-border rounded-lg px-3 py-1.5 text-sm text-text outline-none focus:border-accent" />
                      <span className="text-xs text-text-muted">-1 = auto, 0 = CPU</span>
                    </div>
                  </Field>
                  <Field label="Context Length">
                    <select value={ctxLength} onChange={(e) => { setCtxLength(Number(e.target.value)); setTimeout(saveSettings, 100) }}
                      className="bg-elevated border border-border rounded-lg px-3 py-1.5 text-sm text-text outline-none focus:border-accent">
                      <option value={0}>Auto (recommended)</option>
                      {[2048,4096,8192,16384,32768,65536,131072].map(v => (
                        <option key={v} value={v}>{v.toLocaleString()}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Auto-load last model">
                    <Toggle checked={autoLoad} onChange={setAutoLoad} />
                  </Field>
                </Section>

                <Section title="Sampling Parameters">
                  {isGreedy && (
                    <div className="flex items-center gap-2 px-3 py-2 bg-accent/10 border border-accent/20 rounded-lg text-xs text-accent mb-2">
                      <Zap size={12} /> Greedy mode (temp=0): sampling params ignored
                    </div>
                  )}
                  <SliderField label="Temperature" value={sampling.temperature} min={0} max={2} step={0.05}
                    onChange={(v) => updateSampling('temperature', v)} hint="Higher = more creative" />
                  <SliderField label="Top-P" value={sampling.top_p} min={0.05} max={1} step={0.01}
                    onChange={(v) => updateSampling('top_p', v)} hint="Nucleus sampling" />
                  <SliderField label="Min-P" value={sampling.min_p} min={0} max={1} step={0.01}
                    onChange={(v) => updateSampling('min_p', v)} hint="Min probability threshold" />
                  <Field label="Top-K">
                    <input type="number" value={sampling.top_k} min={0} max={200}
                      onChange={(e) => updateSampling('top_k', Number(e.target.value))}
                      className="w-20 bg-elevated border border-border rounded-lg px-3 py-1.5 text-sm text-text outline-none focus:border-accent" />
                  </Field>
                  <SliderField label="Repeat Penalty" value={sampling.repeat_penalty} min={0.5} max={2} step={0.01}
                    onChange={(v) => updateSampling('repeat_penalty', v)} hint=">1.0 = penalize repeats" />
                  <Field label="Max Tokens">
                    <input type="number" value={sampling.max_tokens} min={64} max={65536} step={256}
                      onChange={(e) => updateSampling('max_tokens', Number(e.target.value))}
                      className="w-24 bg-elevated border border-border rounded-lg px-3 py-1.5 text-sm text-text outline-none focus:border-accent" />
                  </Field>
                  <div className="flex gap-2 pt-1">
                    <button onClick={() => { setSampling(DEFAULT_SAMPLING); setTimeout(saveSettings, 100) }}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-elevated border border-border rounded-lg text-xs text-text-sec hover:border-accent transition-colors">
                      <Trash2 size={11} /> Reset Defaults
                    </button>
                  </div>
                </Section>
              </div>
            )}

            {/* === PROVIDERS TAB === */}
            {activeTab === 'providers' && (
              <div className="space-y-6">
                <Section title="API Providers">
                  <p className="text-xs text-text-muted mb-3">
                    Configure external API providers for cloud models. API keys are stored locally and never sent to our servers.
                  </p>
                  {Object.entries(providers).map(([name, provider]) => (
                    <div key={name} className="bg-elevated/50 rounded-lg p-4 border border-border space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Globe size={14} className="text-text-muted" />
                          <span className="text-sm font-medium text-text capitalize">{name}</span>
                          {provider.enabled && (
                            <span className="text-[10px] px-1.5 py-0.5 bg-green-500/10 text-green-400 border border-green-500/30 rounded-full">
                              Active
                            </span>
                          )}
                        </div>
                        <Toggle checked={provider.enabled} onChange={(v) => {
                          setProviders(prev => ({ ...prev, [name]: { ...prev[name], enabled: v } }))
                          setTimeout(saveSettings, 100)
                        }} />
                      </div>

                      {/* API Key */}
                      <div>
                        <label className="text-xs text-text-muted mb-1 block">API Key</label>
                        <div className="flex gap-2">
                          <div className="relative flex-1">
                            <input
                              type={showKeys[name] ? 'text' : 'password'}
                              value={provider.apiKey}
                              placeholder={`Enter ${name} API key...`}
                              onChange={(e) => {
                                setProviders(prev => ({ ...prev, [name]: { ...prev[name], apiKey: e.target.value } }))
                                setTimeout(saveSettings, 100)
                              }}
                              className="w-full bg-bg border border-border rounded-lg px-3 py-1.5 pr-8 text-sm text-text placeholder-text-muted outline-none focus:border-accent font-mono"
                            />
                            <button
                              onClick={() => setShowKeys(prev => ({ ...prev, [name]: !prev[name] }))}
                              className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text"
                            >
                              {showKeys[name] ? <EyeOff size={14} /> : <Eye size={14} />}
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Endpoint */}
                      <div>
                        <label className="text-xs text-text-muted mb-1 block">Endpoint</label>
                        <input
                          value={provider.endpoint}
                          placeholder="https://api.example.com/v1"
                          onChange={(e) => {
                            setProviders(prev => ({ ...prev, [name]: { ...prev[name], endpoint: e.target.value } }))
                            setTimeout(saveSettings, 100)
                          }}
                          className="w-full bg-bg border border-border rounded-lg px-3 py-1.5 text-sm text-text placeholder-text-muted outline-none focus:border-accent font-mono"
                        />
                      </div>
                    </div>
                  ))}
                </Section>

                <Section title="Local Models">
                  <p className="text-xs text-text-muted">
                    GGUF models loaded from the sidebar run entirely on your hardware.
                    No API key needed. GPU support can be enabled in the Hardware tab.
                  </p>
                </Section>
              </div>
            )}

            {/* === AGENT TAB === */}
            {activeTab === 'agent' && (
              <div className="space-y-6">
                <Section title="Agent Preset">
                  <p className="text-xs text-text-muted mb-2">Choose a preset that controls the agent's tools, steps, and behavior.</p>
                  <AgentPresetGrid preset={preset} onSelect={(p) => { setPreset(p); setTimeout(saveSettings, 100) }} />
                </Section>

                <Section title="System Prompt">
                  <textarea value={systemPrompt} onChange={(e) => { setSystemPrompt(e.target.value); setTimeout(saveSettings, 100) }}
                    placeholder="You are a helpful assistant..."
                    rows={4}
                    className="w-full bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-text-muted outline-none focus:border-accent resize-none" />
                  <p className="text-xs text-text-muted mt-1">Injected as system message at the start of every conversation</p>
                </Section>

                <Section title="Workspace">
                  <div className="flex gap-2">
                    <input value={workspace} onChange={(e) => setWorkspace(e.target.value)}
                      placeholder="Select project folder..." readOnly
                      className="flex-1 bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-text-muted outline-none focus:border-accent font-mono" />
                    <button onClick={handleBrowseWorkspace}
                      className="px-3 py-2 bg-elevated border border-border rounded-lg text-sm text-text-sec hover:border-accent transition-colors">
                      <FolderOpen size={16} />
                    </button>
                  </div>
                  <p className="text-xs text-text-muted mt-1">Agent tools are sandboxed to this folder</p>
                </Section>

                <Section title="Safety">
                  <Field label="Max tool calls per turn">
                    <input type="number" value={maxToolCalls} min={1} max={100}
                      onChange={(e) => { setMaxToolCalls(Number(e.target.value)); setTimeout(saveSettings, 100) }}
                      className="w-20 bg-elevated border border-border rounded-lg px-3 py-1.5 text-sm text-text outline-none focus:border-accent" />
                  </Field>
                  <Field label="Require approval for dangerous tools">
                    <Toggle checked={requireApproval} onChange={(v) => { setRequireApproval(v); setTimeout(saveSettings, 100) }} />
                  </Field>
                  <Field label="Auto-commit on file changes">
                    <Toggle checked={autoCommit} onChange={(v) => { setAutoCommit(v); setTimeout(saveSettings, 100) }} />
                  </Field>
                </Section>

                <Section title="LocalDocs (RAG)">
                  <Field label="Enable RAG">
                    <Toggle checked={ragEnabled} onChange={(v) => { setRagEnabled(v); setTimeout(saveSettings, 100) }} />
                  </Field>
                  {ragEnabled && (
                    <div className="flex gap-2">
                      <input value={ragFolder} onChange={(e) => { setRagFolder(e.target.value); setTimeout(saveSettings, 100) }}
                        placeholder="Document folder path..."
                        className="flex-1 bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-text-muted outline-none focus:border-accent font-mono" />
                      <button onClick={handleBrowseRag}
                        className="px-3 py-2 bg-elevated border border-border rounded-lg text-sm text-text-sec hover:border-accent transition-colors">
                        <FolderOpen size={16} />
                      </button>
                    </div>
                  )}
                </Section>
              </div>
            )}

            {/* === HARDWARE TAB === */}
            {activeTab === 'hardware' && (
              <div className="space-y-6">
                <Section title="GPU Status">
                  {gpuLoading ? (
                    <div className="flex items-center gap-2 text-text-muted text-sm">
                      <RefreshCw size={14} className="animate-spin" /> Checking GPU...
                    </div>
                  ) : gpuStatus ? (
                    <div className="space-y-3">
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${gpuStatus.gpu_available ? 'bg-green-400' : 'bg-text-muted'}`} />
                        <span className="text-sm text-text">
                          {gpuStatus.gpu_available ? 'GPU Available' : 'No GPU Detected'}
                        </span>
                        <span className="text-xs text-text-muted">
                          Status: {gpuStatus.status || 'unknown'}
                        </span>
                      </div>
                      <button onClick={handleGpuInstall} disabled={gpuInstalling}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                          gpuInstalling ? 'bg-accent/20 text-accent' : 'bg-accent text-onAccent hover:bg-accent-hover'
                        }`}>
                        {gpuInstalling ? <><RefreshCw size={14} className="animate-spin" /> Installing...</> : <><Cpu size={14} /> Install GPU Support</>}
                      </button>
                    </div>
                  ) : (
                    <p className="text-sm text-text-muted">Could not detect GPU status</p>
                  )}
                </Section>

                <Section title="System Info">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="bg-elevated/50 rounded-lg p-3">
                      <div className="text-text-muted text-xs mb-1">Platform</div>
                      <div className="text-text">{navigator.platform}</div>
                    </div>
                    <div className="bg-elevated/50 rounded-lg p-3">
                      <div className="text-text-muted text-xs mb-1">Cores</div>
                      <div className="text-text">{navigator.hardwareConcurrency || '?'}</div>
                    </div>
                  </div>
                </Section>
              </div>
            )}

            {/* === APPEARANCE TAB === */}
            {activeTab === 'appearance' && (
              <div className="space-y-6">
                <ThemeSwitcher />
                <Section title="Text">
                  <Field label="Font Size">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-text-muted">10</span>
                      <input type="range" min={10} max={22} value={fontSize}
                        onChange={(e) => { setFontSize(Number(e.target.value)); setTimeout(saveSettings, 100) }}
                        className="flex-1 accent-accent" />
                      <span className="text-xs text-text-muted">22</span>
                      <span className="text-xs text-accent w-8 text-center">{fontSize}px</span>
                    </div>
                  </Field>
                  <Field label="Compact mode">
                    <Toggle checked={compactMode} onChange={(v) => { setCompactMode(v); setTimeout(saveSettings, 100) }} />
                  </Field>
                </Section>
              </div>
            )}

            {/* === KEYBOARD TAB === */}
            {activeTab === 'keyboard' && (
              <div className="space-y-3">
                <p className="text-sm text-text-muted mb-3">Keyboard shortcuts reference</p>
                <div className="space-y-1">
                  {SHORTCUTS.map((s, i) => (
                    <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-elevated/40">
                      <span className="text-sm text-text-sec">{s.action}</span>
                      <kbd className="px-2 py-0.5 bg-elevated border border-border rounded text-xs text-text-muted font-mono">{s.keys}</kbd>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* === PLUGINS TAB === */}
            {activeTab === 'plugins' && (
              <PluginsSettings />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-text mb-3">{title}</h3>
      <div className="space-y-3 pl-1">{children}</div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-text-sec">{label}</span>
      {children}
    </div>
  )
}

function SliderField({ label, value, min, max, step, onChange, hint }: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void; hint?: string
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-text-sec">{label}</span>
        <span className="text-xs text-accent font-mono w-12 text-right">{value.toFixed(2)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-accent" />
      {hint && <p className="text-[10px] text-text-muted mt-0.5">{hint}</p>}
    </div>
  )
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)}
      className={`relative w-9 h-5 rounded-full transition-colors ${checked ? 'bg-accent' : 'bg-border'}`}>
      <div className="absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform"
        style={{ left: checked ? '18px' : '2px' }} />
    </button>
  )
}

const ICON_MAP: Record<string, typeof Bot> = {
  '🔍': Search, '📝': FileText, '♻️': RefreshCw,
  '🐛': Bug, '🚀': Rocket, '⚡': Zap,
}

interface AgentPresetInfo {
  id: string; name: string; description: string; icon: string
  max_steps: number; temperature: number
}

const FALLBACK_PRESETS: AgentPresetInfo[] = [
  { id: 'research', name: 'Research', description: 'Read-only exploration.', icon: '🔍', max_steps: 12, temperature: 0.1 },
  { id: 'code_review', name: 'Code Review', description: 'Structured analysis.', icon: '📝', max_steps: 10, temperature: 0.1 },
  { id: 'refactor', name: 'Refactor', description: 'Safe refactoring.', icon: '♻️', max_steps: 15, temperature: 0.05 },
  { id: 'debug', name: 'Debug', description: 'Error-focused debugging.', icon: '🐛', max_steps: 12, temperature: 0.1 },
  { id: 'full_stack', name: 'Full Stack', description: 'All tools, maximum flexibility.', icon: '🚀', max_steps: 20, temperature: 0.1 },
  { id: 'quick_fix', name: 'Quick Fix', description: 'Fast, minimal changes.', icon: '⚡', max_steps: 4, temperature: 0.05 },
]

function AgentPresetGrid({ preset, onSelect }: { preset: string; onSelect: (id: string) => void }) {
  const [presets, setPresets] = useState<AgentPresetInfo[]>(FALLBACK_PRESETS)

  useEffect(() => {
    agentApi.presets().then((data) => {
      if (data && data.length > 0) setPresets(data)
    }).catch(() => {})
  }, [])

  return (
    <div className="grid grid-cols-2 gap-2">
      {presets.map((p) => {
        const Icon = ICON_MAP[p.icon] || Bot
        const isActive = preset === p.id
        return (
          <button key={p.id} onClick={() => onSelect(p.id)}
            className={`flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-colors ${
              isActive ? 'bg-accent/15 text-accent border border-accent/30' : 'bg-elevated text-text-sec border border-border hover:border-accent/30'
            }`}>
            <Icon size={14} className="mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <div className="text-sm font-medium">{p.name}</div>
              <div className="text-[10px] text-text-muted leading-tight">{p.description}</div>
              <div className="text-[10px] text-text-muted mt-0.5">{p.max_steps} steps · t={p.temperature}</div>
            </div>
          </button>
        )
      })}
    </div>
  )
}

function PluginsSettings() {
  const { plugins, togglePlugin } = usePluginRegistry()
  const categories = [
    { key: 'core', label: 'Core (always on)' },
    { key: 'model', label: 'Model' },
    { key: 'agent', label: 'Agent' },
    { key: 'dev', label: 'Developer' },
    { key: 'collab', label: 'Collaboration' },
  ]
  return (
    <div className="space-y-4">
      <p className="text-sm text-text-muted">Toggle sidebar panels on or off.</p>
      {categories.map((cat) => {
        const catPlugins = plugins.filter((p) => p.category === cat.key)
        if (catPlugins.length === 0) return null
        return (
          <div key={cat.key}>
            <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">{cat.label}</h3>
            <div className="space-y-1">
              {catPlugins.map((plugin) => (
                <div key={plugin.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-elevated/40 transition-colors">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-text-sec font-medium">{plugin.label}</div>
                    <div className="text-[10px] text-text-muted truncate">{plugin.description}</div>
                  </div>
                  <Toggle checked={plugin.enabled} onChange={() => togglePlugin(plugin.id)} />
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}