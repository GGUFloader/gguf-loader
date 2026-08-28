# Changelog

## [3.0.0] - 2026-08-28

### React Frontend Migration

Complete rewrite of the UI from PySide6 (Qt) to React + TypeScript + Tailwind CSS.
The PySide6 UI is still available via `--qt` flag for backward compatibility.

### New Features

#### Backend API Layer (Phase 1)
- FastAPI REST API wrapping existing services
- 25+ endpoints for model, chat, session, agent, files, GPU
- WebSocket handler for real-time streaming

#### React Frontend (Phases 2-7)
- **3-panel layout**: Left (sessions), Center (chat), Right (workbench)
- **Chat UI**: Markdown rendering, syntax highlighting, code copy buttons
- **Streaming**: Token-by-token delivery via WebSocket
- **@ File Mentions**: Type `@` to search and attach workspace files
- **Tool Cards**: Expand/collapse with status icons, args, results
- **Tool Approval**: Modal dialog with risk assessment (low/medium/high)
- **Mode Selector**: Standard, Agent, Minimal, Creator modes
- **Context Lens**: Live token breakdown bar (system/history/tools/free)
- **Metrics Bar**: Duration, tokens, tool calls, cost estimate
- **File Explorer**: Tree view with 30+ file type icons, search
- **Terminal**: Command history, Ctrl+L clear
- **Git Panel**: Status, changed files, inline diff, commit
- **Settings Dialog**: Model, Agent, Appearance, Keyboard tabs
- **Session Navigator**: Search, fork, rename, delete
- **Model Info**: Shows loaded model details in left panel
- **Skeleton Loaders**: For messages, file tree, sessions, terminal
- **Toast Notifications**: Slide-in success/error/warning/info
- **Error Boundary**: Graceful error recovery UI
- **Keyboard Shortcuts**: Ctrl+M, Ctrl+N, Ctrl+B, Ctrl+\, Ctrl+/, Esc

#### Electron Packaging (Phase 8)
- Standalone desktop app (no browser needed)
- Windows NSIS installer, macOS DMG, Linux AppImage
- Spawns Python backend as child process

#### Integration Testing (Phase 11)
- 18 API integration tests covering all endpoints
- WebSocket handler with token-by-token streaming
- Heartbeat, pending approvals queue

#### Code Quality (Phase 14)
- ESLint + Prettier configuration
- GitHub Actions CI pipeline (Python tests + React build)
- TypeScript strict mode

### CLI Changes

```bash
python main.py              # Auto-detect UI mode
python main.py --react      # Force React UI (default)
python main.py --qt         # Force PySide6 UI (legacy)
python main.py --port 3000  # Custom port
python main.py --no-browser # Don't open browser
```

### New Files (66)

```
ggufloader/api/              # FastAPI backend (12 files)
frontend/                    # React frontend (30 files)
electron/                    # Electron packaging (5 files)
tests/test_api_integration.py
docs/REACT_MIGRATION_GUIDE.md
docs/PROJECT_STRUCTURE.md
.github/workflows/ci.yml
CHANGELOG.md
```

### Dependencies Added

**Python:**
- `fastapi` — Web framework
- `uvicorn` — ASGI server

**JavaScript:**
- `react` 19 — UI framework
- `vite` 8 — Build tool
- `tailwindcss` 4 — Styling
- `zustand` — State management
- `react-markdown` — Markdown rendering
- `lucide-react` — Icons
- `electron` — Desktop packaging

---

## [2.2.0] - 2026-08-26

### Agent Mode Improvements
- History processor pipeline
- Reflection loop
- Background summarization
- Context budget management
- Workflow engine
- Benchmarking tools

### UI Enhancements (PySide6)
- Keyboard shortcuts dialog
- Theme customization
- Prompt templates
- JSON export with metadata
- Onboarding wizard
- Model selector
- Chat timeline
- File attachment preview
- Welcome screen
- Floating action button

---

## [2.1.0] - 2026-08-20

### Model Family Auto-Detection
- 39 model families in JSON config
- Auto-detect from filename and GGUF metadata
- Template selection per family
- System prompt support per family

### GPU Management
- GPU install button in UI
- CUDA wheel download with caching
- Memory estimation
- GPU status display

---

## [2.0.0] - 2026-08-15

### Major Release
- Agent mode with tool calling
- Session management (CRUD, fork, search)
- File explorer
- Git integration
- Model parameters dialog
- Advanced settings

---

## [1.0.0] - 2026-01-20

### Initial Release
- GGUF model loading via llama-cpp-python
- Basic chat interface
- GPU offloading
- Model info display
- Session persistence
