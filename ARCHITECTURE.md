# GGUF Loader — Architecture

This document describes how GGUF Loader is structured, how it threads, and how
to extend it. It is aimed at developers who want to contribute features, add
services or tools, or build addons.

**Design goals**

1. **A pure, testable core.** All domain logic (model wrappers, prompt
   formatting, agent loop, tools) lives in `core/` and never imports Qt.
2. **A thin Qt bridge.** `services/` adapts the pure core to Qt's threading and
   signal model. Every background pipeline (model load, chat, agent) runs
   through a service.
3. **Dumb views.** UI panels render state and emit signals; they never call
   into llama.cpp or manage model state directly. `MainWindow` is the only
   object that wires things together (the composition root).
4. **Backward-compatible addons.** The main window exposes the same surface the
   old monolithic window exposed, so existing addons keep working.

---

## 1. Layered overview

```
┌─────────────────────────────────────────────────────────────┐
│  UI layer (ui/, widgets/)             QWidgets, Qt signals  │
│  ChatPanel · SettingsSidebar · MainWindow · ThemeMixin      │
│  widgets: ChatBubble · FeedbackDialog                       │
└───────────────────────────┬─────────────────────────────────┘
                            │ Qt signals (queued, cross-thread)
┌───────────────────────────▼─────────────────────────────────┐
│  Services layer (services/)    QObject + QThread workers    │
│  ModelService · ChatService · AgentService · Environment    │
│  - the only layer that creates threads                      │
└───────────────────────────┬─────────────────────────────────┘
                            │ plain Python calls
┌───────────────────────────▼─────────────────────────────────┐
│  Core layer (core/)              pure Python, no Qt         │
│  llm/     ModelBackend · PromptBuilder                      │
│  agent/   AgentEngine · ToolRegistry (sandboxed tools)      │
└───────────────────────────┬─────────────────────────────────┘
                            │ the *only* direct contact
┌───────────────────────────▼─────────────────────────────────┐
│  llama-cpp-python runtime (llama_cpp.Llama)                 │
└─────────────────────────────────────────────────────────────┘
```

Support modules (not part of the layers but shared by all of them):

- `main.py` — entry point: logging, llama DLL path setup, `QApplication`, opens `MainWindow`.
- `config.py` — constants + `get_paths()`/`ensure_directories()` (creates `models/`, `chats/`, `exports/`, `logs/`, `config/`, `cache/`).
- `resource_manager.py` — resolves paths for the four deployment modes (development, installed package, PyInstaller, frozen exe).
- `addon_manager.py` — discovers and loads addons from `addons/`.
- `utils.py` — small text helpers (e.g. `detect_persian_text`).

### Directory layout

```
main.py                    # Entry point (bootstrap only)
__init__.py                # Package metadata + public API re-exports
config.py                  # Constants + path/directory bootstrap
resource_manager.py        # Deployment-aware path resolution
addon_manager.py           # Addon discovery/loading + sidebar
utils.py                   # Misc helpers

core/                      # PURE domain layer (no Qt)
├── llm/
│   ├── model_backend.py   #   ModelBackend: callable llama wrapper + lock
│   └── prompt_builder.py  #   PromptBuilder: system prompt + history
└── agent/
    ├── tool_registry.py   #   Sandboxed filesystem tools
    └── agent_engine.py    #   Pure agent loop (tools + final answer)

services/                  # Qt bridge layer (QObject + QThread workers)
├── model_service.py       #   Background model load/unload
├── chat_service.py        #   Streaming generation with cooperative stop
└── agent_service.py       #   Background agent turns

ui/                        # Presentation layer
├── main_window.py         #   Composition root + addon-facing API
├── chat_panel.py          #   Message list, input, agent controls
├── sidebar_panel.py       #   Model/GPU/context/appearance settings
└── theme.py               #   Dark/light stylesheets

widgets/                   # Reusable widgets
├── chat_bubble.py         #   Chat message bubble
└── feedback_dialog.py     #   Feedback form (background email send)

addons/                    # Addon packages (see §5)
└── floating_chat/         #   Smart Floating Assistant addon

scripts/                   # Developer/ops scripts (not imported by the app)
build_exe.spec, build_hooks/   # PyInstaller packaging
```

---

## 2. Core layer (`core/`)

**Invariant: nothing in `core/` imports PySide6.** It can be unit-tested
without a display and reused from any thread.

### 2.1 `core/llm/model_backend.py` — `ModelBackend`

The **only module in the application that calls into the `llama_cpp`
runtime**. Everything else — UI, services, addons — goes through
`ModelBackend`. (`resource_manager.get_dll_path()` imports `llama_cpp` too,
but only to locate its DLL directory, never to run inference.)

- `load()` creates the `llama_cpp.Llama` runtime (`n_ctx`, `n_gpu_layers`);
  `unload()` releases it; `is_loaded` reports state.
- **Callable interface:** `backend(prompt, stream=True, ...)` returns a token
  generator; `stream=False` returns a full response dict — the same shape as a
  raw `Llama` object, so legacy callers (including addons) keep working.
- `generate_stream(prompt, **kwargs)` yields plain text tokens; `generate()`
  returns a complete string.
- **Thread safety:** a single `threading.Lock` serializes every call to the
  runtime. The lock is held for the *lifetime of a stream* so two threads can
  never interleave calls into llama.cpp (which crashes). This is why only one
  generation can run at a time app-wide.

### 2.2 `core/llm/prompt_builder.py` — `PromptBuilder`

Pure string formatting. Builds a `User:/Assistant:`-style conversation prompt
from a `system_prompt`, the last 6 history messages, and the new user message.
`stop_tokens()` returns the token-level stop sequences (`</s>`, `user:`,
`assistant:`, …) passed to generation.

### 2.3 `core/agent/tool_registry.py` — `ToolRegistry`

Sandboxed filesystem tools for the agent.

- A `Tool` subclass has a `name`, a `description`, and an
  `execute(params) -> dict` returning `{"status": "success", "result": ...}` or
  `{"status": "error", "error": ...}` (always with `"tool_name"`).
- **Sandbox:** every path is resolved with `Tool.resolve()` relative to one
  workspace root and rejected if it escapes it (path-traversal protection).
- Built-in tools: `list_directory`, `read_file` (BOM/encoding aware, size
  limit), `write_file`, `edit_file` (replace / insert_line / delete_line),
  `search_files`.
- `ToolRegistry.describe()` renders the tool list into the agent system prompt,
  so new tools are advertised automatically.
- `create_default_registry(workspace)` is the convenience factory.

### 2.4 `core/agent/agent_engine.py` — `AgentEngine`

A pure agent loop. It knows nothing about Qt or llama.cpp — it receives a
plain callable `llm(prompt, max_tokens, temperature) -> str`.

Flow per user message (`process(user_message, on_status, on_tool)`):

1. Optional quick analysis for complex requests (status updates via callback).
2. Ask the model for a JSON tool-call plan; parse with `extract_json()`
   (handles ```json fences and bare balanced-brace objects).
3. Execute each tool, streaming status and tool results via callbacks.
4. Ask the model for a natural-language final response (with a deterministic
   fallback if the model returns nothing useful).

The engine keeps its own `conversation_history`; callbacks (`on_status`,
`on_tool`) are how the UI learns about progress. The result dict is
`{"response": str, "tool_results": [...]}`.

---

## 3. Services layer (`services/`)

Services are `QObject`s that expose a signal surface to the UI and run work on
background threads. **All app background pipelines run through this layer.**
(Two legacy `QThread` subclasses — `EmailSenderThread` and `StreamingThread` —
were migrated onto this pattern; no `QThread` subclasses remain in the
codebase.)

### 3.1 The worker pattern (used by the services)

`EnvironmentService` runs the app's own dependency launcher: a fast
synchronous `check()` (interpreter + `requirements.txt` status) plus a
background `run_task("install")` / `run_task("bootstrap")` that streams
`pip` output via the `output` signal and finishes with
`finished(bool, str)` — the same QThread + worker shape as below.

`LauncherService` (plain functions, no Qt) re-exposes the shell utilities
in `scripts/` (GPU install/monitor/verify, EXE build) as one-click
console-window launchers from the sidebar.

(Worker pattern used by all services)

```python
worker = ChatWorker()          # QObject, created in the MAIN thread
worker.prompt = prompt         # arguments = plain attributes
worker.backend = backend
worker.params = params

thread = QThread(self)         # parented to the service (main thread)
worker.moveToThread(thread)

thread.started.connect(worker.process)          # zero-arg @Slot()
worker.token_received.connect(self.token_received.emit)
worker.finished.connect(thread.quit)
thread.finished.connect(worker.deleteLater)
thread.finished.connect(thread.deleteLater)
thread.finished.connect(lambda: self._clear_refs(thread, worker))
thread.start()
```

Rules that make this reliable:

- **Arguments are assigned as attributes before `thread.start()`**, then the
  worker's `process()` is a **zero-arg `@Slot()`**.
  > **Why?** Connecting `thread.started` to a Python lambda silently breaks
  > cross-thread signal delivery in PySide6 — the worker code runs, but
  > nothing it emits ever arrives on the main thread. This was a real bug
  > found during the refactor; attributes + bound slots are the fix.
- **Results flow back exclusively through signals.** Worker signals are
  forwarded to the service's own signals; the UI connects to the service, never
  to the worker.
- **Threads are short-lived:** one `QThread` per request (per model load, per
  generation, per agent turn), quit after the work, deleted with
  `deleteLater`.
- **No stale handles:** `_clear_refs()` drops the service's references when
  the thread finishes, and every `stop()`/shutdown path nulls them — otherwise
  you get `shiboken: QThread already deleted` at exit.

### 3.2 `ModelService`

| Signal | Payload | Meaning |
|---|---|---|
| `loading` | `str` | status text while a load is in progress |
| `loaded` | `ModelBackend` | the ready backend (main thread) |
| `error` | `str` | load failure |
| `unloaded` | — | model released |

- `load(path, use_gpu, n_ctx)` unloads any current model, spawns a
  `ModelLoadWorker`, and returns the built `ModelBackend` via `loaded`.
- The service **owns** the backend (`backend` / `model` properties, `is_loaded`).
- `unload()` stops a pending load and releases the model.

### 3.3 `ChatService`

| Signal | Payload | Meaning |
|---|---|---|
| `started` | — | a generation began |
| `token_received` | `str` | one text token |
| `finished` | — | generation completed |
| `error` | `str` | generation failed |

- `generate(backend, prompt, stop_tokens, **params)` streams tokens.
- **Cooperative stop:** `ChatWorker` checks a `threading.Event` between tokens;
  `service.stop()` sets it, quits, and waits (≤ 2 s).

### 3.4 `AgentService`

Mirrors the engine's callbacks as signals:

| Signal | Payload |
|---|---|
| `response_generated` | `str` — final answer |
| `tool_executed` | `dict` — tool result |
| `status_update` | `str` — progress line |
| `processing_started` / `processing_finished` | — |
| `error_occurred` | `str` |

- `create_engine(backend, workspace)` builds the engine: it wraps
  `backend.generate(...)` in the `llm` callable (with generation params +
  `PromptBuilder.stop_tokens()`), creates a sandboxed `ToolRegistry` for the
  workspace, and returns an `AgentEngine`. The service caches it as `engine`.
- `process_message(engine, message)` runs a turn on a worker thread.

---

## 4. UI layer (`ui/`)

### 4.1 Composition root — `MainWindow`

`MainWindow(QMainWindow, ThemeMixin)` owns everything:

- three services (`_model_service`, `_chat_service`, `_agent_service`),
- a `PromptBuilder` and the `conversation_history` list,
- the panels: `SettingsSidebar` and `ChatPanel`, arranged in a `QSplitter`
  (no addon column — addons are launched from the **Addons menu**),
- a menu bar (File / View / Addons / Help) built by `_build_menu_bar`.

Its own logic is limited to **wiring** (`_wire_services`, `_wire_ui_signals`)
and **state transitions** (model loaded, generation finished, agent init,
theme toggled via `theme_changed`).
`closeEvent` stops the floating-chat addon, then stops chat/agent services and
unloads the model.

### 4.2 Dumb panels

- **`SettingsSidebar`** — emits `load_model_requested`, `dark_mode_toggled`,
  `text_size_changed`, `clear_chat_requested`, `feedback_requested`, … and
  exposes state getters (`get_processing_mode()`, `get_context_size()`) and
  setters (`set_status`, `set_model_info`, `set_loading`). It never touches
  services directly.
- **`ChatPanel`** — renders bubbles (`ChatBubble`), streams tokens
  (`begin_streaming` / `stream_token` / `finish_streaming`), hosts the input
  (`MessageInput`: Enter sends, Shift+Enter is a newline), and the agent-mode
  controls (toggle, workspace combo/browse, status label). Emits
  `message_submitted`, `agent_mode_toggled`, `workspace_selected`.
- **`ThemeMixin`** — `apply_styles()` switches `DARK_STYLESHEET` /
  `LIGHT_STYLESHEET`.

**Convention:** panels never import `services/` or `core/`; they communicate
only through signals and setter methods. This keeps them reusable and makes the
data flow visible in one place (`MainWindow`).

---

## 5. Threading model

```
Thread                            Owns                                   Runs
───────────────────────────────────────────────────────────────────────────────────
Main thread        QApplication, all QWidgets, services,      UI updates, signal
                   ModelBackend handle (owner)                wiring, addons
Worker (load)      ModelLoadWorker (per load)                 ModelBackend(...).load()
Worker (chat)      ChatWorker (per generation)                generate_stream() loop
Worker (agent)     AgentWorker (per turn)                     AgentEngine.process()
```

Key properties:

1. **UI runs only on the main thread.** Qt widgets are never touched from a
   worker.
2. **The model backend is owned by the main thread** (via `ModelService`) but
   *called from* worker threads; `ModelBackend`'s internal lock makes that safe.
3. **All worker→UI communication is via queued signals.** A signal emitted on
   a worker thread with a receiver on the main thread is delivered by the
   event loop, so UI code can safely touch widgets in the connected slot.
4. **One generation at a time.** The lock in `ModelBackend` serializes model
   calls; `ChatService.generate()` and `AgentService.process_message()` also
   stop any in-flight request before starting a new one.
5. **Stop is cooperative.** A `threading.Event` checked between tokens, plus a
   bounded `thread.wait(2000)`.
6. **Clean shutdown.** On `closeEvent`: addon `stop()` → chat/agent
   `stop()` → `ModelService.unload()`; finished threads `deleteLater`
   themselves and the services clear their references.

### Example: a chat message

```
User types in ChatPanel ── message_submitted(text) ──► MainWindow._send_message
                                                          │ model loaded? no → warn
                                                          │ history += user msg
                                                          │ prompt = PromptBuilder.build(...)
                                                          │ ChatPanel.begin_streaming()
                                                          ▼
                                                      ChatService.generate(...)
                                                          │ create ChatWorker (attrs),
                                                          │ moveToThread, thread.start()
                                                          ▼
Worker thread: for token in backend.generate_stream(prompt): emit token_received(token)
                                                          │  (queued to main thread)
                                                          ▼
MainWindow ── token_received ──► ChatPanel.stream_token  (bubble grows, autoscroll)
                                                          │
Worker: emit finished ──► thread.quit ──► _clear_refs      │
                                                          ▼
MainWindow._on_generation_finished ──► finish_streaming() → history += response
                                        generation_finished.emit()  (→ addons)
```

### Example: an agent turn

```
Agent mode on ──► MainWindow._init_agent ──► AgentService.create_engine(backend, workspace)
Message ──► _send_to_agent ──► AgentService.process_message(engine, text)
Worker thread: engine.process(text, on_status=emit status_update, on_tool=emit tool_executed)
  status_update  ──► ChatPanel.add_system_message      (progress lines)
  tool_executed  ──► MainWindow._on_agent_tool_executed (✓/✗ system messages)
  response_generated ──► ChatPanel.add_ai_message
```

---

## 6. Addon system

Addons live in `addons/<name>/` and must expose a `register(parent=None)`
function in their `__init__.py`. `AddonManager` scans the directory, imports
each package, and calls `register(main_window)`; the return value (if any) is
embedded in the main window. Addons are launched from the **Addons menu**
(`AddonManager.open_addon_dialog`), which calls `register(parent)` again.

The `floating_chat` addon shows the **main-window contract** addons rely on:

| Member | Type | Purpose |
|---|---|---|
| `model` | property → `ModelBackend` or `None` | callable, llama-compatible (`model(prompt, stream=True)`); `None` when unloaded |
| `model_loaded` | `Signal(object)` | emitted when a model finishes loading |
| `model_unloaded` | `Signal()` | emitted when the model is released |
| `generation_finished` | `Signal()` | emitted when the main chat completes |
| `generation_error` | `Signal(str)` | emitted when generation fails |
| `theme_changed` | `Signal(bool)` | emitted when dark/light mode is toggled (`True` = dark); addons can connect to restyle themselves |
| `chat_generator` | always `None` | legacy hook; `None` keeps addons on the `model` path |
| `_floating_chat_addon` | attribute | the addon stores its own instance here for lifecycle management |

How the addon finds the window: `register(parent)` checks whether `parent`
(and then its parents, then `QApplication.topLevelWidgets()`) has both
`model` and `model_loaded` attributes. If you build an addon, do the same —
**do not** import `MainWindow` directly, or your addon breaks when the app is
packaged.

---

## 7. How to extend

### 7.1 Add an agent tool

1. Subclass `Tool` in `core/agent/tool_registry.py`:

   ```python
   class CurrentTimeTool(Tool):
       name = "current_time"
       description = "Return the current date and time"

       def execute(self, params):
           import datetime
           return {"status": "success", "result": str(datetime.datetime.now()),
                   "tool_name": self.name}
   ```

2. Register it in `ToolRegistry.__init__` (`self.register(CurrentTimeTool)`).
   It appears in the agent's system prompt automatically via `describe()`.
3. Optional polish: extend `AgentEngine._describe()` and
   `_summarize_result()` (status-line wording) and `MainWindow._on_agent_tool_executed`
   (system-message wording) for the new tool.

### 7.2 Add a service (the pattern)

Follow `ChatService` exactly:

1. **Worker** `QObject` with arg *attributes*, a zero-arg `@Slot() process()`,
   and result signals.
2. **Service** `QObject` with the public signal surface; a
   `start_work(...)` method that stops the previous run, builds the worker,
   `moveToThread`s it, wires `thread.started.connect(worker.process)`,
   forwards worker signals to service signals, quits the thread on completion,
   `deleteLater`s both, and calls `_clear_refs`.
3. Add the stop/cleanup calls to `MainWindow.closeEvent` and wire the new
   signals in `_wire_services`.

### 7.3 Add a UI panel

- Emit signals from the panel; expose setter methods for state; never import
  `services/` or `core/`.
- Add the panel to the splitter in `MainWindow._build_ui()` and connect it in
  `_wire_ui_signals()`.

### 7.4 Write an addon

```
addons/my_addon/
├── __init__.py     # from .main import register
└── main.py         # register(parent=None) -> QWidget | None
```

- Locate the window via `hasattr(parent, "model")`/`model_loaded` (walk
  parents, then `QApplication.topLevelWidgets()`).
- Connect to `model_loaded`, `generation_finished`, `generation_error`, `theme_changed`; call
  `gguf_app.model(prompt, stream=True)` for inference.
- Store your instance on the window (e.g. `gguf_app._my_addon`) and stop it in
  `closeEvent` if needed. See the [Addon Development Guide](https://ggufloader.github.io/docs/addon-development/) for the full guide.

### 7.5 Add configuration

Add constants to `config.py` (they're all documented in the [Configuration Guide](https://ggufloader.github.io/docs/configuration/)).
Runtime-created directories are declared in `get_paths()` /
`ensure_directories()`; `resource_manager.py` decides where they actually live
per deployment mode (dev = project root, exe = `%LOCALAPPDATA%`/`~`).

### 7.6 Packaging

- `scripts/build_exe.bat` → `pyinstaller build_exe.spec`.
- Each package gets a PyInstaller hook in `build_hooks/`
  (`hook-core.py`, `hook-services.py`, `hook-ui.py`, `hook-widgets.py`,
  `hook-addons.py`, `hook-llama_cpp.py`). If you add a top-level package, add
  a hook and a `hiddenimports` entry in `build_exe.spec`.

---

## 8. Testing & validation

- **Core is unit-testable without Qt.** `PromptBuilder`, `ToolRegistry`
  (including sandbox-escape rejection) and `AgentEngine.extract_json`/loop are
  plain Python.
- **Syntax check:** `python -m compileall -q .`
- **Headless GUI smoke test** (no display needed):
  `QT_QPA_PLATFORM=offscreen python -c "from ui.main_window import MainWindow; ..."`.
  Verify: window constructs, addons register, chat pipeline streams tokens and
  finishes, agent pipeline responds, shutdown releases all thread references.
- **Dependencies:** install into `.venv` (`python -m venv .venv`, then
  `pip install -r requirements.txt`); always use `.venv`'s interpreter.

---

**Keep the invariants:** no Qt in `core/` · only `ModelBackend` calls into
llama.cpp · background pipelines run through `services/` (don't add new
`QThread` subclasses) · panels only talk in signals · addons find the window
via duck typing, never by import.
