import { create } from 'zustand'

interface UpdateInfo {
  version: string
  currentVersion: string
  releaseDate: string
  changelog: string
  downloadUrl: string
  size: string
}

interface UpdateState {
  currentVersion: string
  updateAvailable: boolean
  updateInfo: UpdateInfo | null
  checking: boolean
  downloading: boolean
  downloadProgress: number
  lastChecked: number | null
  error: string | null
  panelOpen: boolean
  checkForUpdates: () => Promise<void>
  downloadUpdate: () => Promise<void>
  dismissUpdate: () => void
  togglePanel: () => void
  closePanel: () => void
}

// Current app version (from package.json or hardcoded)
const CURRENT_VERSION = '1.0.0'

export const useUpdateStore = create<UpdateState>((set, get) => ({
  currentVersion: CURRENT_VERSION,
  updateAvailable: false,
  updateInfo: null,
  checking: false,
  downloading: false,
  downloadProgress: 0,
  lastChecked: null,
  error: null,
  panelOpen: false,

  checkForUpdates: async () => {
    set({ checking: true, error: null })
    try {
      // Check GitHub releases API
      const res = await fetch('https://api.github.com/repos/nicepkg/gguf-loader/releases/latest', {
        signal: AbortSignal.timeout(5000),
      })
      if (res.ok) {
        const release = await res.json()
        const latestVersion = release.tag_name?.replace('v', '') || ''
        const currentParts = CURRENT_VERSION.split('.').map(Number)
        const latestParts = latestVersion.split('.').map(Number)

        let isNewer = false
        for (let i = 0; i < 3; i++) {
          if ((latestParts[i] || 0) > (currentParts[i] || 0)) { isNewer = true; break }
          if ((latestParts[i] || 0) < (currentParts[i] || 0)) { break }
        }

        if (isNewer && latestVersion) {
          const asset = release.assets?.[0]
          set({
            updateAvailable: true,
            updateInfo: {
              version: latestVersion,
              currentVersion: CURRENT_VERSION,
              releaseDate: release.published_at?.slice(0, 10) || '',
              changelog: release.body || 'No changelog available',
              downloadUrl: asset?.browser_download_url || release.html_url || '',
              size: asset ? `${(asset.size / 1024 / 1024).toFixed(1)} MB` : 'Unknown',
            },
          })
        } else {
          set({ updateAvailable: false, updateInfo: null })
        }
      } else {
        // API not reachable or no releases — not an error
        set({ updateAvailable: false })
      }
    } catch (e: any) {
      // Network error is fine — just report no update
      set({ updateAvailable: false })
    }
    set({ checking: false, lastChecked: Date.now() })
  },

  downloadUpdate: async () => {
    const { updateInfo } = get()
    if (!updateInfo?.downloadUrl) return

    set({ downloading: true, downloadProgress: 0 })

    try {
      // Open download URL in browser
      window.open(updateInfo.downloadUrl, '_blank')

      // Simulate progress for UX
      let progress = 0
      const interval = setInterval(() => {
        progress += Math.random() * 15
        if (progress >= 100) {
          progress = 100
          clearInterval(interval)
          set({ downloading: false, downloadProgress: 100 })
        }
        set({ downloadProgress: Math.min(progress, 99) })
      }, 500)
    } catch {
      set({ downloading: false, error: 'Download failed' })
    }
  },

  dismissUpdate: () => set({ updateAvailable: false, updateInfo: null }),

  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  closePanel: () => set({ panelOpen: false }),
}))
