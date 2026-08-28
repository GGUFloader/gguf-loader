import { contextBridge, ipcRenderer } from 'electron'

// Expose safe APIs to renderer
contextBridge.exposeInMainWorld('electronAPI', {
  // App info
  getVersion: () => ipcRenderer.invoke('get-app-version'),
  getDataPath: () => ipcRenderer.invoke('get-app-path'),

  // Dialogs
  openFileDialog: () => ipcRenderer.invoke('open-file-dialog'),
  openFolderDialog: () => ipcRenderer.invoke('open-folder-dialog'),

  // Backend control
  restartBackend: () => ipcRenderer.invoke('restart-backend'),

  // Platform info
  platform: process.platform,
  isElectron: true,
})
