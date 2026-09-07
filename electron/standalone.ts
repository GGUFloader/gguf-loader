import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import * as path from 'path'

const BACKEND_URL = process.argv.find(a => a.startsWith('--url='))?.split('=')[1]
  || 'http://localhost:8000'

let mainWindow: BrowserWindow | null = null

function createWindow() {
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, 'icon.ico')
    : path.join(__dirname, '..', '..', 'icon.ico')

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'GGUF Loader',
    icon: iconPath,
    backgroundColor: '#f8f9fa', // light theme default
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  mainWindow.once('ready-to-show', () => mainWindow?.show())

  mainWindow.loadURL(BACKEND_URL)

  // Open external links in the system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
    app.quit()
  })
}

app.whenReady().then(() => {
  createWindow()

  // IPC handlers for file/folder dialogs (needed for browse buttons)
  ipcMain.handle('open-file-dialog', async () => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      properties: ['openFile'],
      filters: [
        { name: 'GGUF Models', extensions: ['gguf'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    })
    return result.filePaths[0] || null
  })

  ipcMain.handle('open-folder-dialog', async () => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      properties: ['openDirectory'],
    })
    return result.filePaths[0] || null
  })
})

app.on('window-all-closed', () => app.quit())
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
