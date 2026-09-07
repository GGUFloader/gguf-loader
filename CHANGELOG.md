# Changelog

## [2.3.0] - 2026-09-04

### The single-model agent build

GGUF Loader is now a **single-model app optimized for Google Gemma 4 12B
Instruct (Q4_K_M)**. All multi-model detection, family profiles, and per-model
prompts were removed, and the agent flow was rebuilt around a strict
planner-driven LangGraph graph.

### Added
- **Auto-load at startup** - the app scans its `models/` folder (plus the
  last-used model folder) and loads the pinned GGUF in the background; the
  manual Load Model step is gone.
- **Model download in the header chip** - when the pinned model is missing the
  chip offers a download with live progress and auto-loads on completion;
  first-launch compatibility dialog.
- **Planner reasoning streams live** ("Planning...") instead of a silent wait.
- **Inline Codebuff-style process UI** - plan steps, tool calls, and results
  render in the chat above each answer; the right-hand progress panel was
  removed.
- **Launch modes** in `launch.bat` / `launch.sh`: browser (default), Electron
  desktop, and production (stale `frontend/dist` is rebuilt automatically).

### Changed
- **Strictly plan-driven agent** - the planner answers directly when no tool
  is needed and writes a step-by-step plan otherwise; the reactive ReAct
  fallback was removed. Every turn ends with the plan's answer step.
- **Tool registry pruned** to the 10 workspace tools the agent uses
  (memory/meta tools removed); `search_files`/`glob` walks are hardened
  against huge generated assets.
- Sampling guardrails tuned for Gemma 4 12B Q4_K_M (`n_ctx=8192` default).
- Docs overhaul - AGENTS.md and ARCHITECTURE.md rewritten for the current
  stack; multi-model/Qt-era docs marked historical; dead links fixed.

### Fixed
- Stray tool-call JSON envelopes are scrubbed from the live stream and the
  final reply (backend + transport level), with regression tests.
- "Planning..." wait status no longer persists as a permanent timeline row.
- WebSocket handlers read live store state, so completed answers always
  replace the streamed text (no duplication, no stale bubbles).

### Notes
- `model_families.json` now contains a single family (`gemma4`, Q4_K_M, 12B).
  A restart is required to apply the new configuration after upgrading.

---

## [3.0.0] - 2026-08-28

### Agent Hardware-Aware Tuning

The agent is now tuned for resource-constrained setups (8 GB VRAM + 32 GB RAM) and stops terminating early with the placeholder "Done." string.

### Added
- Per-model-family tuning profiles (`gemma4`, `gemma3`, `qwen2.5`, `llama3`, `phi3`, `mistral`) in `ggufloader.core.agent.model_profiles`.
- Sidebar controls for `n_batch` (128-2048), `n_threads` (0=auto, 1-32), `n_keep` (64-2048), `flash_attn` toggle.
- Prefill of those controls from the detected model profile on load.
- `n_ctx`, `count_tokens` (`Tokenizer`), and profile defaults wired through `AgentService.create_engine` into `GraphAgent` and `ContextBudget`.
- `max_directive_rounds` configurable on `GraphAgent` (default 3, was 1).

### Changed
- `ModelBackend` constructor accepts the new tuning knobs and passes them to `llama_cpp.Llama(...)`.
- `AgentService.create_engine` reads model profile and threads `max_tokens`/`max_steps`/`json_retries`/`n_ctx`/`max_directive_rounds` into the agent.
- `GraphAgent` defaults lowered (`max_tokens=4096`, `max_steps=16`) to match 8 GB-VRAM Gemma 4 12B Q4_K_M defaults.

### Fixed
- Agent no longer terminates early with "Done." on empty/broken LLM outputs; `_diagnostic` reports step/tool counts.
- Bumped `max_steps` from a model-claimed `estimated_steps` now persists across iterations of the loop.
- Short LLM answers are no longer rejected solely by character count; a tool-evidence requirement gates the early-exit path.
- Agent metrics bar now reflects the engine's actual `max_steps`.

### Target hardware
- Tested profile: 8 GB VRAM, 32 GB RAM, Gemma 4 12B Q4_K_M (`n_ctx=8192`, `n_batch=512`, `n_threads=8`, `n_keep=512`, `flash_attn=on`).

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
