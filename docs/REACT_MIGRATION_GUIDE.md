# GGUF Loader — PySide6 to React Migration Guide

> **📜 Historical document** — describes GGUF Loader at an earlier stage of the
> project and is kept for reference. The current build is a **single-model
> (Gemma 4 12B Q4_K_M)** agent app with a **React/TypeScript frontend and
> FastAPI backend**, running a strictly **plan-driven LangGraph agent** (no
> reactive loop, no multi-model family tuning). UI and architecture details
> below may be outdated.

This guide explains what changed, how to use the new UI, and how to roll back if needed.

## What Changed

GGUF Loader now has **two UI modes**:

| Mode | Technology | When to Use |
|------|-----------|-------------|
| **React** (default) | FastAPI + React + Tailwind | Modern web UI, Electron packaging |
| **PySide6** (legacy) | Qt Desktop | Offline, no browser needed |

The React UI is **the default**. The PySide6 UI is still available with `--qt`.

## Quick Start

### React Mode (Default)

```bash
# Option 1: launch script (recommended)
launch.bat          # Windows
./launch.sh         # macOS/Linux

# Option 2: manual
python main.py

# Option 3: with flags
python main.py --port 3000 --no-browser
```

Open `http://localhost:8000` in your browser.

### PySide6 Mode (Legacy)

```bash
python main.py --qt
```

Or set the environment variable:

```bash
set GGUFLOADER_UI=qt    # Windows
export GGUFLOADER_UI=qt  # macOS/Linux
python main.py
```

## Command-Line Options

| Flag | Description |
|------|-------------|
| `--react` | Launch React web UI (default) |
| `--qt` | Launch PySide6 desktop UI |
| `--port PORT` | Backend port (default: 8000) |
| `--no-browser` | Don't open browser automatically |
| `--version` | Show version |
| `--help` | Show help |

## Architecture Change

### Before (PySide6)
```
python main.py
  → QApplication (PySide6)
  → MainWindow (Qt widgets)
  → llama-cpp-python (in-process)
```

### After (React)
```
python main.py
  → FastAPI server (port 8000)
  → React frontend (served by FastAPI)
  → llama-cpp-python (in-process)
  → WebSocket for streaming
```

## Feature Parity

| Feature | PySide6 | React |
|---------|---------|-------|
| Chat with models | ✅ | ✅ |
| Agent mode | ✅ | ✅ |
| Model loading | ✅ | ✅ |
| GPU management | ✅ | ✅ |
| Session management | ✅ | ✅ |
| File explorer | ✅ | ✅ |
| Terminal | ✅ | ✅ |
| Git panel | ✅ | ✅ |
| Settings | ✅ | ✅ |
| Keyboard shortcuts | ✅ | ✅ |
| Theme customization | ✅ | ✅ |
| Markdown rendering | ✅ | ✅ |
| Code syntax highlighting | ✅ | ✅ |
| Tool approval | ✅ | ✅ |
| Context lens | ❌ | ✅ |
| @ file mentions | ❌ | ✅ |
| Mode selector | ❌ | ✅ |
| Electron packaging | ❌ | ✅ |
| Toast notifications | ✅ | ✅ |

## New Features in React UI

1. **Context Lens** — Live token breakdown bar (system/history/tools/free)
2. **@ File Mentions** — Type `@` to search and attach workspace files
3. **Mode Selector** — Switch between Standard/Agent/Minimal/Creator
4. **Electron Packaging** — Standalone desktop app (Phase 8)
5. **Better Markdown** — Syntax highlighting with copy buttons
6. **Toast Notifications** — Slide-in notifications for actions
7. **Error Boundary** — Graceful error recovery UI
8. **Keyboard Shortcuts** — Ctrl+M, Ctrl+N, Ctrl+B, Ctrl+\, Esc

## Rollback

To go back to the PySide6 UI:

```bash
python main.py --qt
```

Or permanently:

```bash
set GGUFLOADER_UI=qt
```

The PySide6 code is still in `ggufloader/ui/` and `ggufloader/widgets/`.

## Development

### React Frontend Development

```bash
cd frontend
npm install
npm run dev        # Vite dev server on :5173 with hot reload
npm run build      # Build for production
npm run lint       # Run ESLint
```

### Backend Development

```bash
python -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --reload
```

### Running Both

```bash
# Terminal 1: Backend
python -m uvicorn ggufloader.api.app:create_app --factory --port 8000

# Terminal 2: Frontend (proxies API to :8000)
cd frontend && npm run dev
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No model loaded" | Click "Load Model" in left panel |
| Blank page | Make sure backend is running on :8000 |
| Port already in use | Use `--port 3000` to change port |
| PySide6 not found | React mode doesn't need PySide6 |
| FastAPI not found | `pip install fastapi uvicorn` |
| Frontend not built | `cd frontend && npm run build` |
