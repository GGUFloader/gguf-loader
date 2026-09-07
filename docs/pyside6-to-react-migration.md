# Enhanced PySide6 to React Migration Plan

> **📜 Historical document** — describes GGUF Loader at an earlier stage of the
> project and is kept for reference. The current build is a **single-model
> (Gemma 4 12B Q4_K_M)** agent app with a **React/TypeScript frontend and
> FastAPI backend**, running a strictly **plan-driven LangGraph agent** (no
> reactive loop, no multi-model family tuning). UI and architecture details
> below may be outdated.

Based on deep research into OpenHands, DeepSeek Harness, Claude Code WebUI,
LangChain streaming protocol, Inngest AgentKit, and shadcn/ui AI components.

---

## Why React: Industry Evidence

Every production agent harness uses React/TypeScript:
- DeepSeek Harness: React frontend, TypeScript, served at localhost:3080
- OpenHands: React/TypeScript frontend called Agent Canvas
- Claude Code WebUI: React frontend with Deno/Node backend
- shadcn/ui: Ships dedicated AI chat components since June 2026
- LangChain: Provides React SDK for agent streaming
- Inngest AgentKit: useAgent hook for multi-threaded agent conversations

The React ecosystem now has purpose-built components for agent UIs:
- shadcn/ui: MessageScroller, Message, Bubble, Attachment, Marker
- AI Elements: Streaming, status states, type safety for AI apps
- Vercel AI SDK: useChat hook with streaming, tool calls, reasoning
- LangGraph: useStream hook for typed agent events

---
## Architecture: Based on OpenHands Pattern

OpenHands splits into 4 repos with clear boundaries:
1. Frontend (Agent Canvas) - React/TypeScript UI
2. Backend SDK (software-agent-sdk) - Python agent server
3. TypeScript Client - Generated API client
4. Extensions - Skills, automations, integrations

For GGUFLoader, we use a simpler 2-layer architecture:

Python Backend (ggufloader/api/)
  FastAPI server wrapping existing services
  WebSocket for streaming token events
  REST for model/session/agent CRUD
  All existing ggufloader/core/ and services/ untouched

React Frontend (frontend/)
  Vite + React 19 + TypeScript
  shadcn/ui + Tailwind CSS
  Zustand for state management
  Custom useAgent hook for streaming

---

## Streaming Protocol: Based on LangChain Pattern

LangChain defines typed events with channels and namespaces:
- Channels: messages, tools, values, lifecycle, custom:*
- Namespaces: root graph, subgraphs, subagents
- Projections: iterate views you want to render

For GGUFLoader, our WebSocket protocol:

Server sends typed events:
  {type: "token", content: "...", message_id: "..."}
  {type: "reasoning", content: "...", message_id: "..."}
  {type: "tool_call", name: "...", args: {...}, call_id: "..."}
  {type: "tool_result", call_id: "...", output: "...", ms: 123}
  {type: "approval_needed", call_id: "...", tool: "...", risk: "high"}
  {type: "step_complete", number: 3, tokens_used: 1234}
  {type: "message_complete", message_id: "...", total_tokens: 5678}
  {type: "agent_complete", result: "...", total_steps: 5}
  {type: "error", message: "...", recoverable: true}

Client subscribes to channels:
  subscribe(["messages", "tools", "lifecycle"])

---
## React Tech Stack: Exact Versions

Core:
- React 19 (latest, with concurrent features)
- TypeScript 5.5+
- Vite 6 (fast dev server, better than CRA)

Styling:
- Tailwind CSS 4 (utility-first, matches DSH/OpenHands)
- shadcn/ui (Radix UI primitives, ships AI chat components)
- Lucide React (icons, matches shadcn ecosystem)

State Management:
- Zustand (lightweight, OpenHands uses it for conversation/UI state)
- React Query / TanStack Query (server state, caching)

Chat/Streaming:
- Vercel AI SDK useChat (handles streaming, tool calls, reasoning)
- OR custom useAgent hook (like Inngest AgentKit pattern)
- react-markdown + rehype-highlight (markdown rendering)
- Shiki (syntax highlighting, faster than Prism)

Agent-Specific:
- react-resizable-panels (for split panels)
- @xterm/xterm.js (terminal emulation in browser)
- react-diff-viewer-continued (diff display)
- @codemirror/lang-* (code editing in right panel)

---

## React Project Structure

frontend/
  src/
    api/                    # API client layer
      client.ts             # REST API client
      websocket.ts          # WebSocket client
      types.ts              # TypeScript types for API
    components/
      layout/
        AppLayout.tsx        # 3-panel layout shell
        Header.tsx           # Brand + model chip + mode selector
        LeftPanel.tsx        # Sessions navigator
        RightPanel.tsx       # Tabbed workbench
        ContextLens.tsx      # Bottom bar token breakdown
      chat/
        ChatPanel.tsx        # Message list + input area
        MessageList.tsx      # Scrollable message container
        ChatBubble.tsx       # User/AI message bubble
        MessageInput.tsx     # Input with @ mentions, / commands
        ReasoningBlock.tsx   # Expandable thinking block
        StreamingText.tsx    # Live token rendering with cursor
        MarkdownRenderer.tsx # Code blocks, links, tables
      agent/
        AgentPanel.tsx       # Structured agent transcript
        ToolCard.tsx         # Tool call with args/result/time
        ApprovalCard.tsx     # Allow/Deny for dangerous ops
        MetricsBar.tsx       # Steps, tokens, time, retries
        ModeSelector.tsx     # Standard/Code/Minimal/Creator
        ContextChart.tsx     # Token breakdown visualization
      workbench/
        FileExplorer.tsx     # File tree with click to open
        FileEditor.tsx       # CodeMirror-based editor
        Terminal.tsx         # xterm.js terminal emulation
        GitPanel.tsx         # Git status, log, diff
        FileMentionPopup.tsx # @ file mention autocomplete
      shared/
        Toast.tsx            # Notification system
        Skeleton.tsx         # Loading placeholders
        Badge.tsx            # Status badges
    hooks/
      useAgent.ts            # Agent streaming hook
      useWebSocket.ts        # WebSocket connection management
      useModel.ts            # Model state and operations
      useSession.ts          # Session CRUD and switching
      useFileTree.ts         # Workspace file tree
      useKeyboard.ts         # Keyboard shortcuts
    stores/
      modelStore.ts          # Model state (Zustand)
      chatStore.ts           # Chat messages (Zustand)
      sessionStore.ts        # Sessions (Zustand)
      agentStore.ts          # Agent state (Zustand)
      uiStore.ts             # UI state (panels, themes)
    styles/
      globals.css            # Tailwind imports + custom CSS
      themes.ts              # Dark/light theme tokens
  package.json
  tailwind.config.ts
  tsconfig.json
  vite.config.ts

---
## useAgent Hook: The Core Streaming Pattern

Based on Inngest AgentKit and LangChain patterns:

interface UseAgentOptions {
  sessionId: string
  onToken?: (token: string) => void
  onToolCall?: (call: ToolCall) => void
  onApproval?: (approval: ApprovalRequest) => void
  onComplete?: (result: AgentResult) => void
  onError?: (error: AgentError) => void
}

interface UseAgentReturn {
  messages: Message[]
  status: "idle" | "thinking" | "streaming" | "tool_call" | "awaiting_approval"
  sendMessage: (content: string) => void
  stopGeneration: () => void
  approveToolCall: (callId: string) => void
  denyToolCall: (callId: string) => void
  currentToolCalls: ToolCall[]
  metrics: { tokens: number, steps: number, time: number, cost: number }
}

This hook manages:
- WebSocket connection lifecycle
- Token accumulation into messages
- Tool call tracking and approval flow
- Metrics aggregation
- Error recovery and reconnection

---

## Python Backend API: Detailed Design

ggufloader/api/
  __init__.py
  app.py               # FastAPI app with CORS, lifespan
  deps.py              # Dependency injection for services
  routes/
    model.py           # POST /load, DELETE /unload, GET /info
    chat.py            # POST /message (triggers WebSocket stream)
    session.py         # CRUD + fork + search
    agent.py           # start/stop/approve/deny/status
    files.py           # tree, read, write, search
    gpu.py             # install, status
  websocket/
    handler.py         # WebSocket connection manager
    events.py          # Typed event classes
    streaming.py       # Token streaming adapter

Key: Each route file wraps existing services with minimal code.
Example: routes/model.py calls ModelService methods directly.

---
## Migration Phases: Detailed

### Phase 1: Python Backend API (3-4 days)

Day 1: FastAPI app setup
- Create ggufloader/api/app.py with FastAPI, CORS, lifespan
- Create ggufloader/api/deps.py for service injection
- Create ggufloader/api/routes/model.py wrapping ModelService
- Test: POST /api/model/load loads a GGUF file

Day 2: WebSocket streaming
- Create ggufloader/api/websocket/handler.py
- Create ggufloader/api/websocket/streaming.py adapter
- Wire ChatService streaming to WebSocket events
- Test: Connect WebSocket, send message, receive tokens

Day 3: Session and Agent routes
- Create ggufloader/api/routes/session.py wrapping SessionStore
- Create ggufloader/api/routes/agent.py wrapping AgentEngine
- Add session fork endpoint
- Test: CRUD sessions, start/stop agent

Day 4: File and GPU routes
- Create ggufloader/api/routes/files.py for workspace ops
- Create ggufloader/api/routes/gpu.py wrapping GpuInstallService
- Add cross-session search endpoint
- Test: File tree, read/write, GPU status

---

### Phase 2: React Project Setup (1-2 days)

Day 1: Project initialization
- npx create-vite@latest frontend --template react-ts
- cd frontend && npm install
- npm install -D tailwindcss @tailwindcss/vite
- npx shadcn@latest init
- Install: zustand, lucide-react, react-markdown, rehype-highlight
- Install: react-resizable-panels, @xterm/xterm, @codemirror/lang-python

Day 2: Layout and theme
- Create AppLayout.tsx with 3-panel resizable layout
- Set up dark/light theme with Tailwind CSS variables
- Create Header.tsx with brand and model chip
- Create basic LeftPanel.tsx and RightPanel.tsx shells
- Wire REST API client in api/client.ts

---

### Phase 3: Core Chat UI (3-4 days)

Day 1: Message rendering
- Create ChatBubble.tsx with user/AI styling
- Create MarkdownRenderer.tsx with code syntax highlighting
- Create MessageList.tsx with auto-scroll
- Create ChatPanel.tsx composing the above

Day 2: Streaming
- Create useWebSocket.ts hook for connection management
- Create useAgent.ts hook for streaming token accumulation
- Create StreamingText.tsx with live cursor animation
- Wire WebSocket to ChatPanel for real-time rendering

Day 3: Input
- Create MessageInput.tsx with Enter to send
- Add @ file mention popup (FileMentionPopup.tsx)
- Add slash command autocomplete
- Add drag-and-drop file support

Day 4: Reasoning
- Create ReasoningBlock.tsx with expand/collapse
- Wire reasoning tokens from WebSocket to block
- Add thinking animation

---
### Phase 4: Agent UI (2-3 days)

Day 1: Agent panel
- Create AgentPanel.tsx with structured transcript
- Create ToolCard.tsx with collapsible args/result
- Create ApprovalCard.tsx with Allow/Deny buttons
- Wire agent events from WebSocket

Day 2: Metrics and mode
- Create MetricsBar.tsx with live counters
- Create ModeSelector.tsx with Standard/Code/Minimal/Creator
- Create ContextChart.tsx with token breakdown bar
- Wire metrics from WebSocket events

---

### Phase 5: Workbench Panels (3-4 days)

Day 1: Right panel container
- Create RightPanel.tsx with QTabWidget-style tabs
- Create tab switching with keyboard shortcuts
- Add collapsible toggle (Ctrl+B)

Day 2: File explorer and editor
- Create FileExplorer.tsx with tree view
- Create FileEditor.tsx with CodeMirror
- Wire file tree from /api/files/tree
- Wire file read/write from API

Day 3: Terminal and Git
- Create Terminal.tsx with xterm.js
- Wire terminal output from agent tool calls
- Create GitPanel.tsx with status, log, diff
- Auto-refresh after agent changes

---

### Phase 6: Left Panel + Sessions (2 days)

Day 1: Session list
- Create LeftPanel.tsx as slim session navigator
- Create SessionList.tsx with search and right-click menu
- Add session fork from right-click
- Add cross-session search

Day 2: Quick actions
- Add New Chat button
- Add Load Model button
- Add Settings button
- Wire all signals to API calls

---

### Phase 7: Settings + Polish (2-3 days)

Day 1: Settings dialog
- Create SettingsDialog.tsx with tabs
- Model tab: path, context, GPU, parameters
- Agent tab: preset, features, sandbox, approval
- Appearance tab: theme, font, compact mode

Day 2: Context lens and toasts
- Create ContextLens.tsx bottom bar
- Create Toast.tsx notification system
- Add keyboard shortcuts

Day 3: Polish
- Dark/light theme refinement
- Loading skeletons
- Error states
- Responsive layout

---
## Electron Packaging: Standalone Desktop App

Based on OpenHands and Claude Desktop pattern. No browser needed.

### How It Works

User double-clicks GGUFLoader.exe
  Electron main process starts:
  - Spawns Python backend as child process
  - Waits for backend to be ready
  - Opens BrowserWindow pointing to localhost:8000
  - React frontend served by FastAPI

On close:
  - Electron kills Python child process
  - Clean shutdown

### Electron Project Structure

electron/
  main.ts              # Main process
  preload.ts           # IPC preload
  package.json         # Dependencies
  electron-builder.yml # Build config

### Build Commands

cd electron && npm run dev          # Development
npm run build:win                    # Windows exe
npm run build:mac                    # macOS dmg
npm run build:linux                  # Linux AppImage

### Development Mode

Terminal 1: python -m ggufloader.api --reload
Terminal 2: cd frontend && npm run dev
Terminal 3: cd electron && npm run dev

### Distribution

- Windows: GGUFLoader-Setup.exe (~150 MB)
- macOS: GGUFLoader.dmg (~120 MB)
- Linux: GGUFLoader.AppImage (~130 MB)

The exe includes:
- Python runtime
- llama-cpp-python + CUDA DLLs
- FastAPI backend
- React frontend (built)
- All dependencies

---

## File Inventory

### New Electron Files (4 files, ~150 LOC)
electron/main.ts                   # Main process
electron/preload.ts                # IPC preload
electron/package.json              # Dependencies
electron/electron-builder.yml      # Build config

### New Python Files (12 files, ~600 LOC)
ggufloader/api/__init__.py
ggufloader/api/app.py                    # ~80 LOC
ggufloader/api/deps.py                   # ~40 LOC
ggufloader/api/routes/__init__.py
ggufloader/api/routes/model.py           # ~60 LOC
ggufloader/api/routes/chat.py            # ~50 LOC
ggufloader/api/routes/session.py         # ~80 LOC
ggufloader/api/routes/agent.py           # ~60 LOC
ggufloader/api/routes/files.py           # ~70 LOC
ggufloader/api/routes/gpu.py             # ~40 LOC
ggufloader/api/websocket/__init__.py
ggufloader/api/websocket/handler.py      # ~120 LOC

### New React Files (~50 files, ~6,000 LOC)
frontend/src/api/ (3 files)
frontend/src/components/layout/ (5 files)
frontend/src/components/chat/ (7 files)
frontend/src/components/agent/ (6 files)
frontend/src/components/workbench/ (5 files)
frontend/src/components/shared/ (3 files)
frontend/src/hooks/ (6 files)
frontend/src/stores/ (5 files)
frontend/src/styles/ (2 files)
frontend/config files (4 files)

### Files to Delete (~50 PySide6 files, ~13,000 LOC)
ggufloader/ui/ - All 14 UI files
ggufloader/widgets/ - All 36 widget files

### Files to Keep (Python Backend)
ggufloader/core/ - All 59 agent modules
ggufloader/services/ - All services
ggufloader/config.py, utils.py, main.py
ggufloader/addons/ - Addon system

---

## Timeline Summary

| Phase | What | Days | Key Deliverable |
|-------|------|------|-----------------|
| 1 | Backend API Layer | 3-4 | FastAPI + WebSocket server |
| 2 | React Project Setup | 1-2 | Vite + shadcn + Tailwind |
| 3 | Core Chat UI | 3-4 | Streaming chat with markdown |
| 4 | Agent UI | 2-3 | Tool cards, approvals, metrics |
| 5 | Workbench Panels | 3-4 | Files, terminal, git in right panel |
| 6 | Left Panel + Sessions | 2 | Session navigator with fork |
| 7 | Settings + Polish | 2-3 | Unified settings, context lens |
| 8 | Electron Packaging | 2-3 | Standalone exe/dmg/AppImage |
| Total | | 18-25 | |

---

## What GGUFLoader Will Have After Migration

Professional React UI matching DSH/OpenHands/Claude Code:
- 3-panel layout: sessions | chat | workbench
- Streaming tokens with live cursor animation
- Reasoning blocks with expand/collapse
- Tool cards with collapsible args/result
- Approval cards with Allow/Deny
- @ file mention autocomplete
- Context composition chart (token breakdown)
- Runtime mode selector (Standard/Code/Minimal/Creator)
- Integrated terminal (xterm.js)
- Code editor (CodeMirror)
- Git status/diff panel
- Session fork and cross-session search
- Unified settings dialog
- Dark/light theme
- Keyboard shortcuts
- WebSocket streaming (real-time token delivery)

Plus all existing Python backend capabilities preserved:
- Local GGUF model loading
- GPU management
- 59 agent modules
- Session persistence
- Addon system
