# Contributing to GGUF Loader

Thank you for your interest in contributing! This guide covers both the Python backend and React frontend.

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git

### Clone & Install

```bash
git clone https://github.com/GGUFloader/gguf-loader.git
cd gguf-loader

# Python backend
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# React frontend
cd frontend
npm install
cd ..
```

### Run in Development

```bash
# Option 1: Launch script (starts both)
launch.bat  # or ./launch.sh

# Option 2: Manual
# Terminal 1: Backend
python -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --reload

# Terminal 2: Frontend (hot reload)
cd frontend && npm run dev
```

Open http://localhost:5173 (Vite dev server with API proxy).

## Project Structure

```
ggufloader/                     # Backend Python package
├── _version.py                 # Version (single source of truth)
├── config.py                   # Pinned-model identity, chat sampling, paths
├── config/model_families.json  # gemma4 family params + system prompt
├── api/
│   ├── app.py                  # FastAPI factory, CORS, /ws, lifespan
│   ├── auto_load.py            # Startup scan + load pinned GGUF
│   ├── deps.py                 # Dependency injection
│   ├── routes/                 # REST: model, chat, agent, files, gpu
│   └── websocket/handler.py    # /ws endpoint + agent orchestration
├── core/
│   ├── llm/model_backend.py    # THE only llama_cpp.Llama instantiation
│   ├── llm/prompt_builder.py   # Conversation + final-response prompts
│   ├── router.py               # GGUF → LoadStrategy (n_ctx, gpu, batch)
│   ├── system_probe.py         # RAM/VRAM probing
│   └── agent/
│       ├── graph_agent.py      # LangGraph agent (planner/agent/tools)
│       ├── tool_registry.py    # Sandboxed tools (read/write/shell/git)
│       ├── tool_orchestrator.py # Batch execution, retry, approval
│       ├── agent_transport.py  # Status → typed WS events
│       ├── presets.py          # Agent presets (research, refactor, ...)
│       ├── token_cleaner.py    # Gemma channel-token cleaning
│       └── context_budget.py   # Context budgeting + compaction
├── services/                   # Chat, model, GPU services
├── ui/ widgets/                # Legacy PySide6 code (NOT the active UI)
frontend/                       # React + TypeScript + Tailwind
├── src/
│   ├── api/                    # REST + WebSocket client
│   ├── stores/                 # Zustand (chatStore, modelStore, uiStore)
│   ├── hooks/                  # useAgent, useKeyboardShortcuts
│   └── components/
│       ├── layout/             # AppLayout, Header, LeftPanel, RightPanel
│       ├── chat/               # ChatPanel, ChatBubble, MessageInput, StreamingText
│       ├── agent/              # ToolCallCard, ApprovalDialog, ModeSelector
│       ├── workbench/          # FileExplorer, Terminal, GitPanel
│       ├── model/              # ModelLoadDialog
│       ├── settings/           # SettingsDialog
│       └── ui/                 # Skeleton, Toast, ErrorBoundary
├── dist/                       # Production build (served by FastAPI)
electron/                       # Optional Electron shell
tests/unit/                     # Headless pytest suite
```

See [AGENTS.md](AGENTS.md) for the full codebase map and [ARCHITECTURE.md](ARCHITECTURE.md) for the deep dive.

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Run `pytest` before committing

### TypeScript/React

- Use functional components with hooks
- Prefer Zustand stores over prop drilling
- Use Tailwind CSS for styling (no CSS modules)
- Run `npm run lint` and `npm run typecheck` before committing

```bash
cd frontend
npm run lint          # Check for issues
npm run lint:fix      # Auto-fix
npm run typecheck     # TypeScript check
npm run format        # Format with Prettier
```

## Making Changes

### Python Backend

1. Edit files in `ggufloader/api/`, `ggufloader/core/`, or `ggufloader/services/`
2. Add tests in `tests/`
3. Run `python -m pytest tests/ -x`

### React Frontend

1. Edit files in `frontend/src/`
2. Components go in `frontend/src/components/<category>/`
3. State stores go in `frontend/src/stores/`
4. API client functions go in `frontend/src/api/client.ts`
5. Run `npm run build` to verify

### Adding a New API Endpoint

1. Create route in `ggufloader/api/routes/<name>.py`
2. Register in `ggufloader/api/app.py`
3. Add client function in `frontend/src/api/client.ts`
4. Add integration test in `tests/test_api_integration.py`

### Adding a New React Component

1. Create in `frontend/src/components/<category>/<Name>.tsx`
2. Use existing patterns (see `ChatBubble.tsx` or `ToolCallCard.tsx`)
3. Import icons from `lucide-react`
4. Use Tailwind classes for styling

## Testing

### Python Tests

```bash
python -m pytest tests/ -x              # All tests
python -m pytest tests/test_api_integration.py -v  # Integration tests
```

### Frontend Build

```bash
cd frontend
npm run build          # TypeScript + Vite build
npm run typecheck      # TypeScript only
npm run lint           # Lint check
```

## Commit Guidelines

- Use descriptive commit messages
- Reference issue numbers when applicable
- Keep commits focused (one feature/fix per commit)
- Run tests before committing

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`python -m pytest tests/ -x && cd frontend && npm run build`)
5. Commit your changes
6. Push to your fork
7. Open a Pull Request

## Architecture Overview

GGUF Loader is a **single-model (Gemma 4 12B Q4_K_M)** local AI agent app:

- **Backend**: FastAPI + llama-cpp-python (in-process llama.cpp)
- **Frontend**: React + TypeScript + Tailwind, served by FastAPI or Electron
- **Agent**: Strictly plan-driven LangGraph graph (START → planner → agent ↔ tools → END)
- **Streaming**: WebSocket delivers tokens, reasoning, plan steps, and tool results inline

Key files to read:
- `ARCHITECTURE.md` — full architecture deep dive
- `AGENTS.md` — codebase map and conventions
- `ggufloader/core/agent/graph_agent.py` — the LangGraph agent
- `frontend/src/stores/chatStore.ts` — WebSocket event reducer
- `frontend/src/components/chat/ChatPanel.tsx` — chat UI

### Why these choices

- **FastAPI**: async, WebSocket support, auto API docs, serves built frontend
- **LangGraph**: plan/agent/tools nodes with checkpointing, approval interrupts, streaming
- **React + Zustand**: lightweight state, TypeScript-first, Vite HMR
- **Tailwind**: utility-first styling, consistent design system

## Questions?

Open a [Discussion](https://github.com/GGUFloader/gguf-loader/discussions) or email hussainnazary475@gmail.com.
