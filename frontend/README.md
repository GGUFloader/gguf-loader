# GGUF Loader — React Frontend

A modern React/TypeScript frontend for GGUF Loader, matching the UI patterns of DeepSeek Harness, OpenHands, and Claude Code.

## Tech Stack

| Technology | Purpose |
|-----------|---------|
| **React 19** | UI framework |
| **TypeScript** | Type safety |
| **Vite** | Build tool + dev server |
| **Tailwind CSS** | Utility-first styling |
| **Zustand** | State management |
| **react-markdown** | Markdown rendering |
| **Lucide React** | Icons |
| **shadcn/ui** patterns | Component patterns |

## Architecture

```
frontend/src/
├── api/              # REST client + types
│   ├── client.ts     # API functions (model, chat, session, agent, files, gpu)
│   └── types.ts      # TypeScript interfaces
├── stores/           # Zustand state stores
│   ├── chatStore.ts  # Messages, streaming, WebSocket
│   ├── modelStore.ts # Model info, loading state
│   ├── toastStore.ts # Toast notifications
│   └── uiStore.ts    # Theme, panels, agent mode
├── hooks/            # Custom React hooks
│   ├── useAgent.ts   # WebSocket agent hook
│   └── useKeyboardShortcuts.ts
├── components/
│   ├── layout/       # App shell (Header, LeftPanel, RightPanel, AppLayout)
│   ├── chat/         # Chat UI (ChatPanel, ChatBubble, MessageInput, etc.)
│   ├── agent/        # Agent features (ToolCallCard, Approval, ModeSelector, etc.)
│   ├── workbench/    # Right panel (FileExplorer, Terminal, GitPanel, FileViewer)
│   ├── model/        # Model load dialog
│   ├── settings/     # Settings dialog
│   └── ui/           # Shared components (Skeleton, Toast, ErrorBoundary)
└── App.tsx           # Root component
```

## Quick Start

### Prerequisites

- Node.js 18+ (for Vite)
- Python 3.10+ (for backend)

### Development Mode

```bash
# Install dependencies
cd frontend
npm install

# Start dev server (port 5173, proxies API to :8000)
npm run dev
```

The Vite dev server proxies API requests to the Python backend at `localhost:8000`.

### Production Mode

```bash
# Build frontend
cd frontend
npm run build

# Start backend (serves built frontend)
cd ..
python -m uvicorn ggufloader.api.app:create_app --factory --port 8000

# Open http://localhost:8000
```

### Full Launch

```bash
# Windows
launch.bat

# macOS/Linux
chmod +x launch.sh
./launch.sh
```

## Available Scripts

| Script | What It Does |
|--------|-------------|
| `npm run dev` | Start Vite dev server with hot reload |
| `npm run build` | Build for production (outputs to `dist/`) |
| `npm run preview` | Preview production build locally |
| `npm run lint` | Run ESLint |

## API Endpoints

The frontend communicates with these backend endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/model/info` | GET | Current model info |
| `/api/model/load` | POST | Load a GGUF model |
| `/api/model/unload` | DELETE | Unload current model |
| `/api/chat/send` | POST | Send chat message (REST fallback) |
| `/api/sessions` | GET/POST | List/create sessions |
| `/api/sessions/:id` | GET/PUT/DELETE | Get/rename/delete session |
| `/api/sessions/:id/fork` | POST | Fork a session |
| `/api/agent/status` | GET | Agent status |
| `/api/agent/start` | POST | Start agent |
| `/api/agent/stop` | POST | Stop agent |
| `/api/agent/approve` | POST | Approve/deny tool call |
| `/api/files/tree` | GET | Workspace file tree |
| `/api/files/content` | GET | Read file |
| `/api/files/content` | PUT | Write file |
| `/api/files/search` | GET | Search files |
| `/api/files/run` | POST | Execute shell command |
| `/api/files/git/status` | GET | Git status |
| `/api/files/git/diff` | GET | File diff |
| `/api/files/git/commit` | POST | Git commit |
| `/api/gpu/status` | GET | GPU status |
| `/api/gpu/install` | POST | Install GPU support |
| `/ws` | WebSocket | Real-time streaming |

## WebSocket Events

| Event | Direction | Purpose |
|-------|-----------|---------|
| `chat_message` | Client → Server | Send chat message |
| `token` | Server → Client | Streaming text token |
| `reasoning` | Server → Client | Reasoning/thinking block |
| `tool_call` | Server → Client | Tool call started |
| `tool_result` | Server → Client | Tool call result |
| `tool_approval` | Server → Client | Approval request |
| `approve` | Client → Server | Approve/deny tool |
| `message_complete` | Server → Client | Full message done |
| `error` | Server → Client | Error occurred |
| `heartbeat` | Server → Client | Keepalive |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Ctrl+M` | Toggle agent mode |
| `Ctrl+N` | New chat |
| `Ctrl+B` | Toggle left panel |
| `Ctrl+\` | Toggle right panel |
| `Ctrl+/` | Show shortcuts help |
| `Ctrl+K` | Focus search |
| `Esc` | Stop generation |

## Electron Packaging

See `electron/` directory for desktop packaging with Electron.

```bash
cd electron
npm install
npm run dist:win   # Windows installer
npm run dist:mac   # macOS DMG
npm run dist:linux # Linux AppImage
```

## Build Output

```
dist/
├── index.html              # Entry point
└── assets/
    ├── index-[hash].css    # Tailwind + styles (~34 KB)
    └── index-[hash].js     # Bundle (~388 KB, ~116 KB gzip)
```
