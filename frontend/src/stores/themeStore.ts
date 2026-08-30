import { create } from 'zustand'

export interface ThemeColors {
  bg: string
  surface: string
  elevated: string
  border: string
  text: string
  textSec: string
  textMuted: string
  accent: string
  accentHover: string
  success: string
  danger: string
  warning: string
}

export type ThemePreset = 'dark' | 'light' | 'midnight' | 'ocean' | 'forest' | 'sunset' | 'custom'

const PRESETS: Record<ThemePreset, ThemeColors> = {
  dark: {
    bg: '#0b0e14',
    surface: '#12161f',
    elevated: '#1a202c',
    border: '#242c3a',
    text: '#e7ebf2',
    textSec: '#a3adbf',
    textMuted: '#677184',
    accent: '#e8a33d',
    accentHover: '#f0b458',
    success: '#3fbf8a',
    danger: '#e5544b',
    warning: '#e8a33d',
  },
  light: {
    bg: '#f8f9fa',
    surface: '#ffffff',
    elevated: '#f1f3f5',
    border: '#dee2e6',
    text: '#212529',
    textSec: '#495057',
    textMuted: '#868e96',
    accent: '#d9480f',
    accentHover: '#e8590c',
    success: '#2f9e44',
    danger: '#e03131',
    warning: '#f08c00',
  },
  midnight: {
    bg: '#0a0a1a',
    surface: '#0f0f2a',
    elevated: '#16163a',
    border: '#252550',
    text: '#e0e0ff',
    textSec: '#a0a0cc',
    textMuted: '#6060aa',
    accent: '#7c6bff',
    accentHover: '#9580ff',
    success: '#4ade80',
    danger: '#f87171',
    warning: '#fbbf24',
  },
  ocean: {
    bg: '#0c1222',
    surface: '#121a2e',
    elevated: '#1a2540',
    border: '#243050',
    text: '#e0f0ff',
    textSec: '#90b0cc',
    textMuted: '#5070a0',
    accent: '#38bdf8',
    accentHover: '#5cc8fa',
    success: '#34d399',
    danger: '#fb7185',
    warning: '#fbbf24',
  },
  forest: {
    bg: '#0a1410',
    surface: '#0f1f18',
    elevated: '#162a20',
    border: '#1f3a2c',
    text: '#e0f5e8',
    textSec: '#90c8a0',
    textMuted: '#508868',
    accent: '#34d399',
    accentHover: '#5eead4',
    success: '#4ade80',
    danger: '#fb7185',
    warning: '#fbbf24',
  },
  sunset: {
    bg: '#1a0e0e',
    surface: '#241414',
    elevated: '#2e1a1a',
    border: '#3e2525',
    text: '#ffe8e0',
    textSec: '#cc9080',
    textMuted: '#906050',
    accent: '#fb923c',
    accentHover: '#fdba74',
    success: '#4ade80',
    danger: '#f87171',
    warning: '#fbbf24',
  },
  custom: {
    bg: '#0b0e14',
    surface: '#12161f',
    elevated: '#1a202c',
    border: '#242c3a',
    text: '#e7ebf2',
    textSec: '#a3adbf',
    textMuted: '#677184',
    accent: '#e8a33d',
    accentHover: '#f0b458',
    success: '#3fbf8a',
    danger: '#e5544b',
    warning: '#e8a33d',
  },
}

interface ThemeState {
  preset: ThemePreset
  colors: ThemeColors
  reducedMotion: boolean
  setPreset: (preset: ThemePreset) => void
  setCustomColor: (key: keyof ThemeColors, value: string) => void
  setReducedMotion: (v: boolean) => void
}

function applyTheme(colors: ThemeColors) {
  const root = document.documentElement
  root.style.setProperty('--color-bg', colors.bg)
  root.style.setProperty('--color-surface', colors.surface)
  root.style.setProperty('--color-elevated', colors.elevated)
  root.style.setProperty('--color-border', colors.border)
  root.style.setProperty('--color-text', colors.text)
  root.style.setProperty('--color-text-sec', colors.textSec)
  root.style.setProperty('--color-text-muted', colors.textMuted)
  root.style.setProperty('--color-accent', colors.accent)
  root.style.setProperty('--color-accent-hover', colors.accentHover)
  root.style.setProperty('--color-success', colors.success)
  root.style.setProperty('--color-danger', colors.danger)
  root.style.setProperty('--color-warning', colors.warning)

  // Determine color scheme
  const brightness = getBrightness(colors.bg)
  root.style.setProperty('color-scheme', brightness > 0.5 ? 'light' : 'dark')

  // Set reduced motion
  root.classList.toggle('reduce-motion', useThemeStore.getState().reducedMotion)
}

function getBrightness(hex: string): number {
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  return 0.299 * r + 0.587 * g + 0.114 * b
}

export const useThemeStore = create<ThemeState>((set) => ({
  preset: 'dark',
  colors: { ...PRESETS.dark },
  reducedMotion: false,

  setPreset: (preset) => {
    const colors = { ...PRESETS[preset] }
    set({ preset, colors })
    applyTheme(colors)
    try { localStorage.setItem('ggufloader_theme', preset) } catch {}
  },

  setCustomColor: (key, value) => {
    set((s) => {
      const colors = { ...s.colors, [key]: value }
      applyTheme(colors)
      return { colors, preset: 'custom' }
    })
  },

  setReducedMotion: (v) => {
    set({ reducedMotion: v })
    document.documentElement.classList.toggle('reduce-motion', v)
    try { localStorage.setItem('ggufloader_reduced_motion', String(v)) } catch {}
  },
}))

// Initialize from localStorage
export function initTheme() {
  try {
    const saved = localStorage.getItem('ggufloader_theme') as ThemePreset
    if (saved && PRESETS[saved]) {
      useThemeStore.getState().setPreset(saved)
    }
    const rm = localStorage.getItem('ggufloader_reduced_motion')
    if (rm === 'true') {
      useThemeStore.getState().setReducedMotion(true)
    }
  } catch {}
}

export const THEME_PRESETS: { id: ThemePreset; name: string; preview: string[] }[] = [
  { id: 'dark', name: 'Dark', preview: ['#0b0e14', '#e8a33d'] },
  { id: 'light', name: 'Light', preview: ['#f8f9fa', '#d9480f'] },
  { id: 'midnight', name: 'Midnight', preview: ['#0a0a1a', '#7c6bff'] },
  { id: 'ocean', name: 'Ocean', preview: ['#0c1222', '#38bdf8'] },
  { id: 'forest', name: 'Forest', preview: ['#0a1410', '#34d399'] },
  { id: 'sunset', name: 'Sunset', preview: ['#1a0e0e', '#fb923c'] },
]
