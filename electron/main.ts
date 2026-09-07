import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron'
import * as path from 'path'
import { spawn, execSync, ChildProcess } from 'child_process'
import * as net from 'net'

let mainWindow: BrowserWindow | null = null
let backendProcess: ChildProcess | null = null
let viteProcess: ChildProcess | null = null
let viteReady = false
const BACKEND_PORT = 8000
const VITE_PORT = 5173
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`
const VITE_URL = `http://localhost:${VITE_PORT}`

// Resolve paths for development vs packaged
function getBackendPath(): string {
  if (app.isPackaged) {
    // Packaged: Python is a sidecar
    return path.join(process.resourcesPath, 'backend', 'python.exe')
  }
  // Development: use system Python
  return 'python'
}

function getBackendArgs(): string[] {
  if (app.isPackaged) {
    return [path.join(process.resourcesPath, 'backend', 'start.py')]
  }
  return ['-m', 'uvicorn', 'ggufloader.api.app:create_app', '--factory', '--port', String(BACKEND_PORT)]
}

function getFrontendURL(): string {
  if (app.isPackaged || !viteReady) {
    return BACKEND_URL
  }
  // Development: Vite dev server
  return VITE_URL
}

// Wait for backend to be ready
function waitForBackend(timeoutMs = 30000): Promise<void> {
  return new Promise((resolve, reject) => {
    const startTime = Date.now()
    const interval = setInterval(() => {
      const socket = net.createConnection(BACKEND_PORT, 'localhost')
      socket.on('connect', () => {
        socket.destroy()
        clearInterval(interval)
        resolve()
      })
      socket.on('error', () => {
        socket.destroy()
        if (Date.now() - startTime > timeoutMs) {
          clearInterval(interval)
          reject(new Error('Backend startup timeout'))
        }
      })
    }, 500)
  })
}

function startVite(): Promise<void> {
  return new Promise((resolve, reject) => {
    const frontendDir = app.isPackaged
      ? null
      : path.join(__dirname, '..', '..', 'frontend')

    if (!frontendDir) {
      resolve()
      return
    }

    console.log('Starting Vite dev server...')
    viteProcess = spawn('npm', ['run', 'dev'], {
      cwd: frontendDir,
      shell: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, FORCE_COLOR: '0' },
    })

    viteProcess.stdout?.on('data', (data) => {
      const line = data.toString().trim()
      console.log(`[vite] ${line}`)
      // Vite prints 'Local: http://localhost:5173' when ready
      if (line.includes('localhost:') && line.includes(String(VITE_PORT))) {
        resolve()
      }
    })

    viteProcess.stderr?.on('data', (data) => {
      console.error(`[vite] ${data.toString().trim()}`)
    })

    viteProcess.on('error', (err) => {
      console.error('Vite process error:', err)
      reject(err)
    })

    viteProcess.on('exit', (code) => {
      console.log(`Vite exited with code ${code}`)
      viteProcess = null
    })

    // Timeout after 30 seconds
    setTimeout(() => {
      reject(new Error('Vite dev server startup timeout'))
    }, 30000)
  })
}

function startBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    const cmd = getBackendPath()
    const args = getBackendArgs()
    const cwd = app.isPackaged
      ? path.join(process.resourcesPath, 'backend')
      : path.join(__dirname, '..', '..')

    console.log(`Starting backend: ${cmd} ${args.join(' ')}`)
    console.log(`CWD: ${cwd}`)

    backendProcess = spawn(cmd, args, {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        GGUFLOADER_PORT: String(BACKEND_PORT),
      },
    })

    backendProcess.stdout?.on('data', (data) => {
      console.log(`[backend] ${data.toString().trim()}`)
    })

    backendProcess.stderr?.on('data', (data) => {
      console.error(`[backend] ${data.toString().trim()}`)
    })

    backendProcess.on('error', (err) => {
      console.error('Backend process error:', err)
      reject(err)
    })

    backendProcess.on('exit', (code) => {
      console.log(`Backend exited with code ${code}`)
      backendProcess = null
    })

    // Wait a moment for the process to start, then check connectivity
    setTimeout(() => {
      waitForBackend()
        .then(resolve)
        .catch(reject)
    }, 1000)
  })
}

function killByPort(port: number) {
  try {
    const result = execSync(`netstat -ano | findstr :${port} | findstr LISTENING`, { encoding: 'utf-8' })
    const pids = new Set<string>()
    for (const line of result.split('\n')) {
      const match = line.trim().split(/\s+/).pop()
      if (match && match !== '0') pids.add(match)
    }
    for (const pid of pids) {
      try { execSync(`taskkill /PID ${pid} /F`, { stdio: 'ignore' }) } catch {}
    }
  } catch {}
}

function stopVite() {
  if (viteProcess) {
    console.log('Stopping Vite dev server...')
    try { viteProcess.kill() } catch {}
    killByPort(VITE_PORT)
    viteProcess = null
  }
}

function stopBackend() {
  if (backendProcess) {
    console.log('Stopping backend...')
    try { backendProcess.kill() } catch {}
    killByPort(BACKEND_PORT)
    backendProcess = null
  }
}

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
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    backgroundColor: '#f8f9fa', // light theme default
    show: false, // Show after ready
  })

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  // Load the frontend
  const frontendURL = getFrontendURL()
  console.log(`Loading frontend: ${frontendURL}`)
  mainWindow.loadURL(frontendURL)

  // Open DevTools in development
  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

// App lifecycle
async function waitForURL(url: string, timeoutMs = 30000): Promise<void> {
  return new Promise((resolve, reject) => {
    const startTime = Date.now()
    const check = async () => {
      try {
        const http = await import('http')
        const req = http.get(url, (res) => {
          res.resume()
          resolve()
        })
        req.on('error', () => {
          if (Date.now() - startTime > timeoutMs) {
            reject(new Error(`Timeout waiting for ${url}`))
          } else {
            setTimeout(check, 500)
          }
        })
        req.setTimeout(2000, () => {
          req.destroy()
          if (Date.now() - startTime > timeoutMs) {
            reject(new Error(`Timeout waiting for ${url}`))
          } else {
            setTimeout(check, 500)
          }
        })
      } catch {
        if (Date.now() - startTime > timeoutMs) {
          reject(new Error(`Timeout waiting for ${url}`))
        } else {
          setTimeout(check, 500)
        }
      }
    }
    check()
  })
}

app.whenReady().then(async () => {
  try {
    // Check if backend is already running
    const portInUse = await new Promise<boolean>((resolve) => {
      const socket = net.createConnection(BACKEND_PORT, 'localhost')
      socket.on('connect', () => { socket.destroy(); resolve(true) })
      socket.on('error', () => { socket.destroy(); resolve(false) })
      setTimeout(() => { socket.destroy(); resolve(false) }, 1000)
    })

    if (portInUse) {
      console.log(`Backend already running on port ${BACKEND_PORT}`)
    } else {
      console.log('Starting Python backend...')
      await startBackend()
      console.log('Backend ready')
    }

    // In dev mode, also start Vite
    if (!app.isPackaged) {
      try {
        console.log('Starting Vite dev server...')
        await startVite()
        viteReady = true
        console.log('Vite ready')
      } catch (err) {
        console.warn('Vite failed to start, falling back to backend:', err)
      }
    }

    // Create the window
    createWindow()

    // Wait for frontend to be ready, then load it
    const url = getFrontendURL()
    await waitForURL(url)
    mainWindow?.loadURL(url)
  } catch (err) {
    console.error('Failed to start:', err)
    dialog.showErrorBox(
      'GGUF Loader',
      `Failed to start the backend server.\n\n${err}\n\nMake sure Python 3.10+ is installed and in your PATH.`
    )
    app.quit()
  }
})

app.on('window-all-closed', () => {
  stopVite()
  stopBackend()
  app.quit()
})

app.on('before-quit', () => {
  stopVite()
  stopBackend()
  // Safety: force-kill anything left on our ports after 2s
  setTimeout(() => {
    killByPort(BACKEND_PORT)
    killByPort(VITE_PORT)
    process.exit(0)
  }, 2000)
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})

// IPC handlers
ipcMain.handle('get-app-version', () => app.getVersion())
ipcMain.handle('get-app-path', () => app.getPath('userData'))

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

ipcMain.handle('restart-backend', async () => {
  stopBackend()
  await startBackend()
  return true
})
