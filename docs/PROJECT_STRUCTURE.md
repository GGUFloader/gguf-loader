# GGUF Loader — Project Structure

## Overview

GGUF Loader is a **universal GGUF model loader** with a built-in plan-driven agent:
- **React UI**: FastAPI backend + React frontend (the only UI)
- **Agent**: Plan-driven LangGraph agent with sandboxed tools
- **Note**: v2.3.0 is a testing release temporarily pinned to Gemma 4 12B Instruct Q4_K_M; universal model support returns next release

## Directory Layout

```
gguf-loader/
├── main.py                          # Entry point (auto-detects React/Qt)
├── launch.bat                       # Windows launcher
├── launch.sh                        # macOS/Linux launcher
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Package config
│
├── ggufloader/                      # Python package
│   ├── __init__.py
│   ├── main.py                      # App entry point (React or Qt)
│   ├── config.py                    # Configuration management
│   ├── resource_manager.py          # DLL/icon/config paths
│   ├── logging_setup.py             # File logging with rotation
│   │
│   ├── api/                         # FastAPI backend (NEW)
│   │   ├── __init__.py
│   │   ├── app.py                   # FastAPI app + SPA serving
│   │   ├── deps.py                  # Dependency injection
│   │   ├── routes/
│   │   │   ├── model.py             # /api/model/* endpoints
│   │   │   ├── chat.py              # /api/chat/* endpoints
│   │   │   ├── session.py           # /api/sessions/* endpoints
│   │   │   ├── agent.py             # /api/agent/* endpoints
│   │   │   ├── files.py             # /api/files/* + git + terminal
│   │   │   └── gpu.py               # /api/gpu/* endpoints
│   │   └── websocket/
│   │       └── handler.py           # WebSocket streaming handler
│   │
│   ├── core/                        # Core business logic
│   │   ├── agent/                   # Agent engine
│   │   ├── llm/                     # LLM backend, model profiles
│   │   └── sessions/                # Session store
│   │
│   ├── services/                    # Application services
│   │   ├── model_service.py         # Model loading/unloading
│   │   ├── chat_service.py          # Chat generation
│   │   └── gpu_install_service.py   # GPU installation
│   │
│   ├── config/                      # Configuration files
│   │   └── model_families.json      # gemma4 family (single model)
│
├── frontend/                        # React frontend (NEW)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── README.md
│   │
│   ├── src/
│   │   ├── App.tsx                  # Root component
│   │   ├── main.tsx                 # Entry point
│   │   ├── index.css                # Tailwind + theme vars
│   │   │
│   │   ├── api/                     # REST client
│   │   │   ├── client.ts            # API functions
│   │   │   └── types.ts             # TypeScript interfaces
│   │   │
│   │   ├── stores/                  # Zustand state
│   │   │   ├── chatStore.ts         # Messages + WebSocket
│   │   │   ├── modelStore.ts        # Model state
│   │   │   ├── toastStore.ts        # Toast notifications
│   │   │   └── uiStore.ts           # UI state
│   │   │
│   │   ├── hooks/                   # Custom hooks
│   │   │   ├── useAgent.ts          # WebSocket agent hook
│   │   │   └── useKeyboardShortcuts.ts
│   │   │
│   │   └── components/
│   │       ├── layout/              # App shell
│   │       │   ├── AppLayout.tsx     # 3-panel layout
│   │       │   ├── Header.tsx        # Brand + model chip + mode
│   │       │   ├── LeftPanel.tsx     # Sessions + model info
│   │       │   └── RightPanel.tsx    # Tabbed workbench
│   │       │
│   │       ├── chat/                # Chat UI
│   │       │   ├── ChatPanel.tsx     # Message list + input
│   │       │   ├── ChatBubble.tsx    # Message bubble
│   │       │   ├── MessageInput.tsx  # Input with @mentions
│   │       │   ├── StreamingText.tsx # Live streaming
│   │       │   ├── ReasoningBlock.tsx
│   │       │   ├── MarkdownRenderer.tsx
│   │       │   └── FileMentionPopup.tsx
│   │       │
│   │       ├── agent/               # Agent features
│   │       │   ├── ToolCallCard.tsx
│   │       │   ├── ToolApprovalDialog.tsx
│   │       │   ├── ToolApprovalPanel.tsx
│   │       │   ├── ModeSelector.tsx
│   │       │   ├── AgentMetricsBar.tsx
│   │       │   └── ContextLens.tsx
│   │       │
│   │       ├── workbench/           # Right panel tabs
│   │       │   ├── FileExplorer.tsx
│   │       │   ├── FileViewer.tsx
│   │       │   ├── Terminal.tsx
│   │       │   └── GitPanel.tsx
│   │       │
│   │       ├── model/
│   │       │   └── ModelLoadDialog.tsx
│   │       │
│   │       ├── settings/
│   │       │   └── SettingsDialog.tsx
│   │       │
│   │       └── ui/
│   │           ├── Skeleton.tsx
│   │           ├── Toast.tsx
│   │           └── ErrorBoundary.tsx
│   │
│   └── dist/                        # Built output (gitignored)
│
├── electron/                        # Electron packaging (NEW)
│   ├── main.ts                      # Main process
│   ├── preload.ts                   # Secure IPC bridge
│   ├── package.json
│   ├── tsconfig.json
│   └── electron-builder.yml         # Build config
│
├── tests/                           # Test suite
│   ├── test_*.py                    # 240 tests
│   └── test_api_integration.py      # 18 API integration tests
│
├── docs/                            # Documentation
│   ├── REACT_MIGRATION_GUIDE.md
│   ├── PROJECT_STRUCTURE.md
│   ├── deepseek-harness-ui-comparison.md
│   ├── ui-upgrade-plan.md
│   └── pyside6-to-react-migration.md
│
├── icon.ico                         # App icon
├── screenshots/                      # UI screenshots for README
│   ├── screen1.png
│   ├── screen2.png
│   └── screen3.png
```

## Key Architectural Decisions

### 1. Backend stays Python
All business logic (model loading, chat, sessions, agent) remains in Python. Only the UI layer changed from PySide6 to React.

### 2. FastAPI wraps existing services
The `ggufloader/api/` layer is thin — it imports existing services and exposes them as REST endpoints.

### 3. WebSocket for streaming
Chat responses stream token-by-token over WebSocket, not REST polling.

### 4. Zustand for state
Lightweight state management — no Redux overhead. Three stores: chat, model, UI.

### 5. Single UI
The React app running in FastAPI is the only UI. The legacy PySide6 code is no longer shipped.

### 6. Vite dev server proxies to FastAPI
In development, Vite runs on :5173 and proxies `/api/*` to FastAPI on :8000.

### 7. Built frontend served by FastAPI
In production, `app.py` serves `frontend/dist/` with SPA fallback routing.

## File Counts

| Category | Files | LOC |
|----------|-------|-----|
| Backend API | 12 | ~600 |
| React Frontend | 30 | ~2,500 |
| Electron | 5 | ~400 |
| Tests | 1 (new) | ~150 |
| Docs | 3 (new) | ~500 |
| Entry point | 1 | ~140 |
| Config | 1 | ~10 |
| **Total New** | **53** | **~4,300** |
| Core/Services | 59 | ~12,000 |
| **Grand Total** | **~105** | **~17,000** |
