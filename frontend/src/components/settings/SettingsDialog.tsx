import { useState } from 'react'
import {
  X,
  Bot,
  Palette,
  Keyboard,
  Cpu,
  Sliders,
  Monitor,
  Moon,
  Sun,
} from 'lucide-react'
import { useUIStore } from '../../stores/uiStore'

interface Props {
  onClose: () => void
}

const TABS = [
  { id: 'model', label: 'Model', icon: Cpu },
  { id: 'agent', label: 'Agent', icon: Bot },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'keyboard', label: 'Keyboard', icon: Keyboard },
]

const ACCENT_COLORS = [
  { name: 'Amber', value: '#f59e0b' },
  { name: 'Blue', value: '#3b82f6' },
  { name: 'Purple', value: '#8b5cf6' },
  { name: 'Pink', value: '#ec4899' },
  { name: 'Green', value: '#22c55e' },
  { name: 'Cyan', value: '#06b6d4' },
  { name: 'Orange', value: '#f97316' },
  { name: 'Red', value: '#ef4444' },
]

const SHORTCUTS = [
  { keys: 'Enter', action: 'Send message' },
  { keys: 'Shift+Enter', action: 'New line' },
  { keys: '@', action: 'Mention file' },
  { keys: '/', action: 'Slash commands' },
  { keys: 'Ctrl+M', action: 'Toggle agent mode' },
  { keys: 'Esc', action: 'Stop generation' },
  { keys: 'Ctrl+/', action: 'Keyboard shortcuts' },
  { keys: 'Ctrl+K', action: 'Focus search' },
  { keys: 'Ctrl+N', action: 'New chat' },
  { keys: 'Ctrl+B', action: 'Toggle left panel' },
  { keys: 'Ctrl+\\', action: 'Toggle right panel' },
  { keys: 'Ctrl+L', action: 'Clear terminal' },
]

export function SettingsDialog({ onClose }: Props) {
  const [activeTab, setActiveTab] = useState('model')
  const { theme, toggleTheme } = useUIStore()

  // Model settings state
  const [gpuLayers, setGpuLayers] = useState(-1)
  const [ctxLength, setCtxLength] = useState(32768)
  const [autoLoad, setAutoLoad] = useState(false)

  // Agent settings state
  const [preset, setPreset] = useState('standard')
  const [maxToolCalls, setMaxToolCalls] = useState(20)
  const [requireApproval, setRequireApproval] = useState(true)
  const [autoCommit, setAutoCommit] = useState(false)

  // Appearance state
  const [fontSize, setFontSize] = useState(14)
  const [compactMode, setCompactMode] = useState(false)
  const [accentColor, setAccentColor] = useState('#f59e0b')

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface border border-border rounded-xl shadow-2xl w-[680px] max-h-[80vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Sliders size={18} className="text-accent" />
            <h2 className="text-base font-semibold text-text">Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text rounded-lg hover:bg-elevated transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Tab sidebar */}
          <div className="w-40 border-r border-border py-2 space-y-0.5">
            {TABS.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'bg-accent/10 text-accent font-medium'
                      : 'text-text-sec hover:bg-elevated'
                  }`}
                >
                  <Icon size={15} />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {activeTab === 'model' && (
              <div className="space-y-5">
                <Section title="Model Loading">
                  <Field label="GPU Layers (-1 = auto)">
                    <input
                      type="number"
                      value={gpuLayers}
                      onChange={(e) => setGpuLayers(Number(e.target.value))}
                      className="w-24 bg-elevated border border-border rounded-lg px-3 py-1.5 text-sm text-text outline-none focus:border-accent"
                    />
                  </Field>
                  <Field label="Context Length">
                    <select
                      value={ctxLength}
                      onChange={(e) => setCtxLength(Number(e.target.value))}
                      className="bg-elevated border border-border rounded-lg px-3 py-1.5 text-sm text-text outline-none focus:border-accent"
                    >
                      <option value={2048}>2,048</option>
                      <option value={4096}>4,096</option>
                      <option value={8192}>8,192</option>
                      <option value={16384}>16,384</option>
                      <option value={32768}>32,768</option>
                      <option value={65536}>65,536</option>
                      <option value={131072}>131,072</option>
                    </select>
                  </Field>
                  <Field label="Auto-load last model">
                    <Toggle checked={autoLoad} onChange={setAutoLoad} />
                  </Field>
                </Section>
              </div>
            )}

            {activeTab === 'agent' && (
              <div className="space-y-5">
                <Section title="Agent Preset">
                  <div className="grid grid-cols-2 gap-2">
                    {['standard', 'agent', 'minimal', 'creator'].map((p) => (
                      <button
                        key={p}
                        onClick={() => setPreset(p)}
                        className={`px-3 py-2 rounded-lg text-sm capitalize transition-colors ${
                          preset === p
                            ? 'bg-accent/15 text-accent border border-accent/30'
                            : 'bg-elevated text-text-sec border border-border hover:border-accent/30'
                        }`}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </Section>
                <Section title="Safety">
                  <Field label="Max tool calls per turn">
                    <input
                      type="number"
                      value={maxToolCalls}
                      onChange={(e) => setMaxToolCalls(Number(e.target.value))}
                      className="w-24 bg-elevated border border-border rounded-lg px-3 py-1.5 text-sm text-text outline-none focus:border-accent"
                    />
                  </Field>
                  <Field label="Require approval for dangerous tools">
                    <Toggle checked={requireApproval} onChange={setRequireApproval} />
                  </Field>
                  <Field label="Auto-commit on file changes">
                    <Toggle checked={autoCommit} onChange={setAutoCommit} />
                  </Field>
                </Section>
              </div>
            )}

            {activeTab === 'appearance' && (
              <div className="space-y-5">
                <Section title="Theme">
                  <Field label="Mode">
                    <div className="flex gap-2">
                      {[
                        { id: 'dark', icon: Moon, label: 'Dark' },
                        { id: 'light', icon: Sun, label: 'Light' },
                        { id: 'system', icon: Monitor, label: 'System' },
                      ].map((t) => (
                        <button
                          key={t.id}
                          onClick={() => theme !== t.id && toggleTheme()}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors ${
                            theme === t.id
                              ? 'bg-accent/15 text-accent border border-accent/30'
                              : 'bg-elevated text-text-sec border border-border hover:border-accent/30'
                          }`}
                        >
                          <t.icon size={13} />
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </Field>
                </Section>
                <Section title="Accent Color">
                  <div className="flex gap-2 flex-wrap">
                    {ACCENT_COLORS.map((c) => (
                      <button
                        key={c.value}
                        onClick={() => setAccentColor(c.value)}
                        className={`w-7 h-7 rounded-full border-2 transition-all ${
                          accentColor === c.value
                            ? 'border-white scale-110'
                            : 'border-transparent hover:scale-105'
                        }`}
                        style={{ backgroundColor: c.value }}
                        title={c.name}
                      />
                    ))}
                  </div>
                </Section>
                <Section title="Text">
                  <Field label="Font Size">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-text-muted">10</span>
                      <input
                        type="range"
                        min={10}
                        max={22}
                        value={fontSize}
                        onChange={(e) => setFontSize(Number(e.target.value))}
                        className="flex-1 accent-accent"
                      />
                      <span className="text-xs text-text-muted">22</span>
                      <span className="text-xs text-accent w-8 text-center">{fontSize}px</span>
                    </div>
                  </Field>
                  <Field label="Compact mode">
                    <Toggle checked={compactMode} onChange={setCompactMode} />
                  </Field>
                </Section>
              </div>
            )}

            {activeTab === 'keyboard' && (
              <div className="space-y-3">
                <div className="text-sm text-text-muted mb-3">
                  Keyboard shortcuts reference
                </div>
                <div className="space-y-1">
                  {SHORTCUTS.map((s, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-elevated/40"
                    >
                      <span className="text-sm text-text-sec">{s.action}</span>
                      <kbd className="px-2 py-0.5 bg-elevated border border-border rounded text-xs text-text-muted font-mono">
                        {s.keys}
                      </kbd>
                    </div>
                  ))}
                </div>
              </div>
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

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-9 h-5 rounded-full transition-colors ${
        checked ? 'bg-accent' : 'bg-border'
      }`}
    >
      <div
        className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
          checked ? 'translate-x-4.5' : 'translate-x-0.5'
        }`}
        style={{ left: checked ? '18px' : '2px' }}
      />
    </button>
  )
}
