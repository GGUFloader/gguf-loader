import { useState } from 'react'
import { Palette, Check, Eye, EyeOff } from 'lucide-react'
import { useThemeStore, THEME_PRESETS, type ThemeColors } from '../../stores/themeStore'

const COLOR_LABELS: Record<keyof ThemeColors, string> = {
  bg: 'Background',
  surface: 'Surface',
  elevated: 'Elevated',
  border: 'Border',
  text: 'Text',
  textSec: 'Secondary Text',
  textMuted: 'Muted Text',
  accent: 'Accent',
  accentHover: 'Accent Hover',
  success: 'Success',
  danger: 'Danger',
  warning: 'Warning',
}

export function ThemeSwitcher() {
  const { preset, colors, reducedMotion, setPreset, setCustomColor, setReducedMotion } = useThemeStore()
  const [showCustom, setShowCustom] = useState(false)

  return (
    <div className="space-y-4">
      {/* Preset selector */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Palette size={14} className="text-accent" />
          <span className="text-xs font-medium text-text">Theme</span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {THEME_PRESETS.map(p => (
            <button
              key={p.id}
              onClick={() => setPreset(p.id)}
              className={`relative flex flex-col items-center gap-1.5 p-2 rounded-lg border transition-all ${
                preset === p.id
                  ? 'border-accent bg-accent/10'
                  : 'border-border bg-elevated hover:border-accent/30'
              }`}
            >
              {/* Color preview dots */}
              <div className="flex gap-1">
                <div className="w-4 h-4 rounded-full border border-white/10" style={{ backgroundColor: p.preview[0] }} />
                <div className="w-4 h-4 rounded-full border border-white/10" style={{ backgroundColor: p.preview[1] }} />
              </div>
              <span className="text-[10px] text-text-sec">{p.name}</span>
              {preset === p.id && (
                <div className="absolute top-1 right-1">
                  <Check size={10} className="text-accent" />
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Custom colors */}
      <div>
        <button
          onClick={() => setShowCustom(!showCustom)}
          className="text-xs text-accent hover:text-accent-hover transition-colors"
        >
          {showCustom ? 'Hide custom colors' : 'Customize colors'}
        </button>
        {showCustom && (
          <div className="mt-2 space-y-1.5 bg-elevated border border-border rounded-lg p-3">
            {Object.entries(COLOR_LABELS).map(([key, label]) => (
              <div key={key} className="flex items-center gap-2">
                <input
                  type="color"
                  value={(colors as any)[key]}
                  onChange={(e) => setCustomColor(key as keyof ThemeColors, e.target.value)}
                  className="w-6 h-6 rounded border border-border cursor-pointer"
                  aria-label={`${label} color`}
                />
                <span className="text-[10px] text-text-sec flex-1">{label}</span>
                <span className="text-[9px] text-text-muted font-mono">{(colors as any)[key]}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Reduced motion */}
      <div className="flex items-center justify-between bg-elevated border border-border rounded-lg px-3 py-2">
        <div className="flex items-center gap-2">
          {reducedMotion ? <EyeOff size={14} className="text-text-muted" /> : <Eye size={14} className="text-accent" />}
          <div>
            <div className="text-xs text-text">Reduce Motion</div>
            <div className="text-[10px] text-text-muted">Disable animations for accessibility</div>
          </div>
        </div>
        <button
          onClick={() => setReducedMotion(!reducedMotion)}
          className={`relative w-10 h-5 rounded-full transition-colors ${reducedMotion ? 'bg-accent' : 'bg-border'}`}
          role="switch"
          aria-checked={reducedMotion}
          aria-label="Toggle reduced motion"
        >
          <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${reducedMotion ? 'translate-x-5' : 'translate-x-0.5'}`} />
        </button>
      </div>
    </div>
  )
}
