# GGUF Loader — Architecture v2 (12-Month Target)

This document is the *target architecture* for the next 12 months. It is
the plan everything else (current `ARCHITECTURE.md`, per-feature PRs,
phase work) converges on. It assumes the product direction: a local-first
desktop AI assistant whose flagship capability is a **LangGraph agent
that actually does tasks** on the user's files, powered by **llama.cpp**
as the only inference engine.

Current `ARCHITECTURE.md` documents the *present* design; this document
is the *future* design. Read both.

---

## 0. Principles (the non-negotiables)

1. **llama.cpp is the engine, forever.** Every LLM/embedding call in the
   app goes through one engine interface; `llama-cpp-python` is the only
   implementation for the foreseeable future. Backends are an adapter
   detail, not a product feature.
2. **The agent is a LangGraph graph.** State, nodes, edges, checkpointing,
   human-in-the-loop interrupts, and streaming come from LangGraph. We do
   not hand-roll the loop a second time.
3. **Local-first and private by default.** No cloud, no telemetry, no
   analytics. Network tools exist only behind explicit user config.
4. **Safety by default.** Workspace jail for every tool; anything
   executable, destructive, or network-bound requires human approval.
5. **Stream everything, cancel everything.** No blocking LLM call may
   leave the user staring at a frozen UI.
6. **Graceful degradation, never silent failure.** If a 7B model can't
   produce valid tool JSON, we repair, retry, then fall back to plain
   chat — and we *say* what happened. A silent no-op is a bug.
7. **Core is pure; UI is thin; services are bridges.** Everything
   testable without Qt lives outside the UI. Qt only renders and forwards.
8. **One model at a time, serialized execution.** llama.cpp owns one GPU
   context; all inference funnels through a single executor.
9. **Extensibility is a first-class feature.** Tools, backends, memory
   providers, and addons all have documented extension points.
10. **The 7B-class model is the real user.** Prompts, schemas, retries,
    and defaults are tuned for small local models, not for GPT-4.

---

## 1. Target directory layout

```
GGUF Loader/
├── main.py                  # bootstrap only (QApplication + composition)
├── launch.sh / launch.bat   # dependency management (unchanged philosophy)
├── config.py                # static constants only (no runtime state)
├── core/                    # pure Python, no Qt
│   ├── engine/              # model runtime abstraction
│   │   ├── protocol.py      #   ModelEngine, ChatDelta, EngineInfo (Protocol)
│   │   ├── llama_cpp_engine.py   #   the one real implementation
│   │   └── langchain_adapter.py  #   BaseChatModel wrapper for LangGraph
│   ├── agent/               # LangGraph agent
│   │   ├── graph.py         #   StateGraph: nodes, edges, router
│   │   ├── state.py         #   AgentState TypedDict + reducers
│   │   ├── prompts.py       #   system prompt, schemas, few-shot, repair
│   │   ├── json_protocol.py #   extract_json, repair loop (moved from engine)
│   │   └── tools/           # tool SDK + catalog
│   │       ├── sdk.py       #   AgentTool ABC, ToolContext, ToolResult, categories
│   │       ├── filesystem.py#   list/read/write/edit/search/move/delete/glob
│   │       ├── command.py   #   run_command (approval-gated)
│   │       ├── git.py       #   git wrapper (approval-gated)
│   │       ├── memory.py    #   remember / recall / ask_workspace
│   │       └── user.py      #   ask_user (interrupt)
│   ├── memory/              # persistence for the agent + conversations
│   │   ├── store.py         #   SQLite stores (conversations, memories, settings)
│   │   ├── embeddings.py    #   embed engine wrapper + cosine search
│   │   └── undo.py          #   copy-before-write snapshots
│   └── settings/            # settings schema, load/save, defaults
├── services/                # Qt bridges (one per concern)
│   ├── engine_service.py    #   owns the ModelEngine lifecycle (load/unload/swap)
│   ├── chat_service.py      #   streams chat tokens (evolved from today)
│   ├── agent_service.py     #   runs the LangGraph graph, forwards events
│   ├── approval_service.py  #   human-in-the-loop interrupt ↔ UI dialog
│   ├── memory_service.py    #   conversation + long-term memory access
│   ├── settings_service.py  #   settings load/save, defaults, change events
│   └── session_service.py   #   conversation list, resume, export
├── ui/
│   ├── app_context.py       #   composition root object (replaces MainWindow god-object)
│   ├── main_window.py       #   window chrome + menu only
│   ├── chat_panel.py        #   message stream (today + transcript rendering)
│   ├── agent_panel.py       #   plan / steps / tool results / diffs / approvals
│   ├── settings_dialog.py   #   model, GPU, workspace, permissions
│   └── memory_browser.py    #   browse long-term memories per workspace
├── persistence/             # thin SQLite access layer (open/close, WAL)
├── addons/                  # formalized addon API over AppContext
├── scripts/                 # GPU install/verify/monitor (unchanged)
└── tests/
    ├── unit/                # engine adapter, graph, tools, memory, settings
    ├── integration/         # real-model smoke tests (slow, marked)
    └── gui/                 # pytest-qt offscreen smoke tests
```

---

## 2. Engine layer (`core/engine`)

### 2.1 The interface

```python
class ModelEngine(Protocol):
    def load(self, path: str, *, gpu: bool, n_ctx: int) -> "EngineHandle": ...
    def chat(self, messages: list[dict], *, stream: bool, **params)
        -> str | Iterator[ChatDelta]: ...
    def complete(self, prompt: str, *, stream: bool, **params)
        -> str | Iterator[ChatDelta]: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def info(self) -> EngineInfo: ...          # offloaded layers, device, VRAM
    def unload(self) -> None: ...
```

- `ChatDelta`: `{token, finish_reason}` — one shape for both chat and
  agent streaming.
- `EngineInfo`: `{model_path, n_ctx, use_gpu, offloaded_layers,
  total_layers, device, vram_mb}` — the "provable GPU" story from the GPU
  plan lives here. `offloaded_layers` is captured from llama.cpp's log
  during load (Phase 1 of the GPU plan).
- **Why a Protocol:** the chat UI, the agent, and embeddings all share it;
  tests inject fakes; an Ollama/OpenAI-compatible server backend becomes a
  drop-in later without touching UI or agent code.

### 2.2 The implementation

`llama_cpp_engine.py` wraps `llama_cpp.Llama`:
- `chat()` → `Llama.create_chat_completion(...)` (chat template handled by
  llama.cpp; we stop fighting templates).
- `complete()` → raw completion for prompt-style work.
- `embed()` → `Llama.create_embedding(...)`. Embeddings use a **separate
  embed engine instance** (small embed GGUF) that loads on demand and
  unloads when idle, because llama.cpp keeps one model per process.
- Serialization: all calls go through the single engine executor (see §5),
  so the internal lock is a backstop, not the design.

### 2.3 The LangChain adapter

`langchain_adapter.py` implements `langchain_core.language_models.
BaseChatModel` over `ModelEngine.chat`:
- `_generate` / `_stream` over the engine; `bind_tools` is **not**
  required — the agent uses our JSON protocol prompt (see §3.4), so the
  adapter stays small and works with any 7B GGUF.
- This is the only place LangChain touches the engine. LangGraph talks to
  the adapter; everything else talks to `ModelEngine` directly.

---

## 3. Agent layer (`core/agent`) — the centerpiece

### 3.1 State

```python
class AgentState(TypedDict, total=False):
    messages: Annotated[list[Message], add_messages]   # user/assistant/tool
    step_count: int
    tool_results: list[ToolResult]
    plan: list[str] | None
    workspace: str
    budget: int                 # max steps (default 8)
    model_params: dict          # temperature, max_tokens, ...
```

Checkpointed per conversation by `langgraph-checkpoint-sqlite`, so
conversations resume, replay (time-travel) is possible in dev, and memory
is crash-safe.

### 3.2 The graph

```
        START
          │
          ▼
      [plan] ──(complex?)──► [agent] ◄──────────────────┐
          │                     │                       │
          │              tool_calls? ──no + answer──► [finish] ──► END
          │                     │ yes
          │                     ▼
          │               [needs_approval?]
          │                     │
          │        yes          ▼            no
          │        ┌───── [approve] ◄── interrupt: UI dialog
          │        │          │ resume
          │        └──────────┤
          │                   ▼
          │               [tools]
          │                   │  results appended to state
          │                   │  step_count += 1
          │                   └── step_count >= budget? ──► [finish]
          └──────────────────────┘
```

- **`plan` (conditional):** for complex requests, one extra node produces
  a numbered step list shown in the transcript. Skip for simple asks.
- **`agent`:** one LLM call via the adapter. Internal logic is our proven
  Phase-A machinery: schema prompt + few-shot → `extract_json` → repair
  loop (≤2 repairs) → returns `{tool_calls?, answer?}`. No repair path
  falls back to plain chat and says so.
- **`needs_approval` (router):** inspects the tool batch. Tools whose
  category is `command`/`git`/`network`/`delete`, or writes outside the
  workspace, or whose policy says "ask" → route to `approve`; otherwise
  straight to `tools`.
- **`approve`:** a LangGraph **interrupt** node. The graph pauses; the UI
  shows the exact command/target/risk with Allow/Deny/Edit; the graph
  resumes with `Command(resume=decision)`. Denied calls are marked
  "blocked by user" and fed back to the agent.
- **`tools`:** executes the batch via `ToolRegistry`; every result is
  appended to state (and shown in the transcript). Failed calls trigger
  the failure-driven corrective retry from Phase A, bounded by the
  signature guard.
- **`finish`:** produces the natural-language final answer from the last
  `answer` or from accumulated tool results. Budget-exhausted runs land
  here too, with an honest "reached step limit" note.

### 3.3 Streaming & cancellation

- `graph.stream(..., stream_mode=["messages", "updates", "custom"])`:
  - `messages` → token deltas → the live AI bubble (chat and agent share
    the streaming renderer).
  - `updates` → node transitions (plan, tool starts/results, approvals).
  - `custom` → status/step events from nodes.
- Cancellation: `AgentService` runs the graph on a worker thread with a
  stop flag checked at node boundaries and inside the engine stream
  (`ChatDelta` carries a cancel check). LangGraph's async cancellation is
  available for a future async path; the Qt path stays thread-based.

### 3.4 Why the JSON protocol (not native function calling)

llama-cpp-python's function calling is unreliable on 7B GGUF models. The
schema-rich JSON protocol (already implemented in Phase A) is more robust
for small models and is engine-agnostic. LangGraph doesn't require
`bind_tools`; the `agent` node produces tool calls however it wants.
Decision: **keep JSON protocol.** Revisit only if a much stronger model
becomes the default.

### 3.5 Tool SDK

```python
class AgentTool(ABC):
    name: str
    description: str
    schema: dict                      # JSON schema (Phase A format)
    category: ToolCategory            # read | write | command | git | network | memory | user
    requires_approval: bool = False

    def execute(self, ctx: ToolContext, params: dict) -> ToolResult: ...
    def preview(self, params: dict) -> str: ...   # shown in the approval dialog
```

`ToolContext`: `{workspace, engine, memory, settings, undo, session}`.
Tools are plain classes registered into `ToolRegistry`; third parties can
ship tools as addons (§7).

**Tool catalog, year one:**

| Category | Tool | Approval | Quarter |
|---|---|---|---|
| read | `list_directory`, `read_file`, `search_files`, `glob` | no | now / Q1 |
| write | `write_file`, `edit_file` (replace/insert/delete) | no (undo always) | now |
| write | `move_file`, `copy_file`, `delete_file`, `apply_patch` | yes (delete/patch) | Q1 |
| command | `run_command` (sandboxed shell, cwd=workspace, timeout, streamed output, output cap) | yes | Q1 |
| git | `git_status`, `git_diff`, `git_commit`, `git_checkout` | yes | Q1 |
| memory | `remember`, `recall`, `ask_workspace` (RAG over workspace) | no | Q2 |
| user | `ask_user` (interrupt with a question) | n/a (it IS the interrupt) | Q2 |
| network | `web_fetch` (allowlist), optional `search_web` (needs config) | yes | Q3 |

Exit criterion for "actually does tasks": the agent can, in one turn,
scaffold a small project in the workspace, write tests, run them with
`run_command`, read the output, fix failures, and summarize — all
streamed, all approve-gated.

### 3.6 Memory

- **Short-term:** graph state + checkpointer (per conversation).
- **Long-term:** SQLite `memories(workspace, key, text, embedding BLOB,
  created_at, updated_at)`; `remember(key, text)` upserts; `recall(query)`
  embeds the query and returns top-k by cosine similarity. No external
  vector DB — a few hundred memories is trivially searchable in Python.
- **Workspace RAG (Q2):** `ask_workspace` indexes workspace docs on
  demand into the same store and answers from retrieved chunks. The embed
  engine (§2.2) powers all of it.

### 3.7 Safety model

- Every tool resolves paths inside the workspace jail (already true) or
  an explicitly user-approved absolute path.
- Approval tiers: `never-ask` (reads, in-workspace writes), `ask`
  (default for command/git/network/delete), `always-allow` (per
  session, persisted per workspace in settings).
- `run_command` constraints: cwd locked to workspace; default timeout
  120s; stdout capped (last 64 KB); no user secrets in env; command
  shown verbatim in the approval dialog with a `preview()` explanation.
- Undo: `undo.py` snapshots files before any write/edit/delete
  (timestamped, one per operation); a `revert` tool + UI button restores.
- Prompt-injection stance: tool output is untrusted data. Tool messages
  are marked in state; tool text can never override system instructions;
  anything executable still passes through approval regardless of what
  injected text claims.

---

## 4. Application layer (`services/` + `ui/`)

### 4.1 Composition root — `AppContext`

Replaces the MainWindow-as-god-object pattern with one plain object:

```python
class AppContext:
    settings: SettingsService
    engine: EngineService            # owns ModelEngine lifecycle
    chat: ChatService
    agent: AgentService
    approval: ApprovalService
    memory: MemoryService
    sessions: SessionService
    events: EventBus                 # Qt signals for cross-cutting events
    paths: dict[str, Path]
```

`MainWindow` becomes chrome + menu; panels are constructed with the
context they need. Addons receive `AppContext` (not the window), which
formalizes the addon API (`register(ctx) -> QWidget | None`) and kills the
`hasattr(gguf_app, "model")` discovery dance.

### 4.2 Services (Qt bridges)

- **EngineService:** load/unload/swap models; reports `EngineInfo`; owns
  the executor thread (§5).
- **ChatService:** streams chat deltas (evolved from today; same stop
  semantics, already hardened against the deleted-thread race).
- **AgentService:** runs the graph, maps `stream_mode` events to Qt
  signals (`token_received`, `status_update`, `tool_executed`,
  `approval_requested`, `step_changed`, `finished`).
- **ApprovalService:** owns the interrupt↔dialog bridge; emits
  `approval_requested(ApprovalRequest)` and resumes the graph with the
  decision.
- **SessionService:** conversation list, resume, export (Markdown/JSON).
- **MemoryService:** read/write long-term memories; query embeddings.

### 4.3 UI

- **ChatPanel:** the message stream (today). Agent messages render inline.
- **AgentPanel (new):** a structured transcript — plan steps, per-tool
  cards (params, duration, result, diff), approval cards, step counter,
  Cancel button. Free-text status lines become structured events.
- **SettingsDialog (new):** model path + presets, GPU toggle + install
  (existing), context length, workspace defaults, permission policy,
  "always allow" management.
- **MemoryBrowser (new):** per-workspace memories, search, delete.
- Model chip (header) shows `EngineInfo`: "GPU 32/32 · 5.2 GB VRAM" or
  "CPU" (GPU plan Phase 1).

---

## 5. Threading & execution model

One serialized **engine executor** thread: a queue fed by chat, agent,
and memory calls; each request streams deltas back via Qt signals;
cooperative cancel flag per request. Benefits:

- Removes per-request `QThread` spawning (and the deleted-object race
  class entirely — the current `isValid` guards stay as a backstop).
- Single lock at the engine (backstop only).
- Agent graph runs on its own worker thread *driving* the executor; the
  graph's step boundaries are natural cancel points.

`EngineService` owns the executor; workers never touch Qt objects except
through signals.

---

## 6. Persistence

| Data | Store | Notes |
|---|---|---|
| settings | `settings.json` (config dir) | theme, GPU pref, context, workspace prefs, permission policy, model presets |
| conversations | SQLite `conversations` (WAL) | id, title, created/updated, workspace, model, messages JSON |
| agent checkpoints | SQLite (langgraph-checkpoint-sqlite) | keyed by conversation id |
| long-term memories | SQLite `memories` | embeddings BLOB + cosine search |
| undo snapshots | workspace `.gguf-undo/` | timestamped copies |
| logs | logs dir, rotating | existing |

All SQLite files live under the resource-managed data dir
(`%LOCALAPPDATA%/GGUFLoader` on Windows, `~/.ggufloader` on POSIX —
already handled by `resource_manager`).

---

## 7. Addons & extensions

- Addon contract becomes `register(ctx: AppContext) -> QWidget | None`
  with lifecycle `start()/stop()` (floating chat already conforms).
- New extension points: **tools** (AgentTool subclass + registry entry),
  **memory providers** (optional), **UI panels** (context menu slot).
- The floating chat addon becomes a second surface over the same services
  (it already calls `gguf_app.model`; it will call `ctx.engine` instead).

---

## 8. Packaging & distribution

- Launcher scripts stay the dependency manager (hardened already).
- `requirements.txt` grows: `langgraph`, `langchain-core` (pulls pydantic
  v2). **Open decision:** the frozen EXE currently *excludes* pydantic
  (~300 MB saving). With LangGraph in the picture we either (a) include
  pydantic and accept a bigger EXE, or (b) ship the EXE without the agent
  and keep the agent in the launcher/venv build. Recommendation: (a) —
  the agent is the flagship; keep UPX + other excludes to offset size.
- GPU: existing install/detect/toggle stays; add an opt-in GPU EXE build
  variant (build flag) so EXE users aren't silently CPU-bound (GPU plan
  Phase 3).
- Auto-update (Q4): check GitHub releases, download installer, verify
  checksum, apply on next launch.

---

## 9. Testing & quality

- **Unit (fast, CI):** engine adapter against a fake engine; graph nodes,
  router, budget, repair, and retry with the fake-LLM harness (already
  proven); tool sandbox (path escape, encoding, size caps); memory store;
  settings; undo.
- **Integration (slow, opt-in):** real-model tests — chat streams,
  one agent tool turn, embedding + recall. Marked `@pytest.mark.slow`.
- **GUI:** pytest-qt offscreen smoke tests (boot, panels, agent
  transcript render).
- **CI:** add a `test.yml` workflow (unit + lint on Python 3.11/3.12,
  Windows + Linux matrix). Keep `build-release.yml` as-is.
- The fake-LLM harness is the backbone of agent tests: it must stay
  trivial to script (list of responses), so every graph change is
  testable in milliseconds.

---

## 10. Non-functional goals

- **Latency:** stream everything; llama.cpp KV/prompt caching for repeat
  prefixes; warm model across turns.
- **VRAM:** `EngineInfo` surfaced; context auto-fit warnings before load;
  graceful full→partial→CPU fallback (GPU plan Phase 1).
- **Reliability:** crash-safe SQLite (WAL); thread guards; all user-facing
  errors translated from raw CUDA/llama errors to plain language.
- **Observability:** structured agent transcript is itself the debug
  log; `--debug` dumps graph state snapshots.

---

## 11. Roadmap (12 months)

### Q1 (Months 1–3) — Solidify core, ship the real agent
- M1: test suite + CI (`test.yml`); finish Phase A already in progress.
- M1–2: `core/engine` (Protocol + LlamaCppEngine + LangChain adapter);
  LangGraph migration: state, nodes, router, SQLite checkpointer,
  streaming (`messages`/`updates`/`custom`), cancel; keep JSON protocol.
- M2–3: `run_command` + git tools behind the approval interrupt; undo
  snapshots; AgentPanel transcript UI (steps, tool cards, approvals).
- M3: settings service + `AppContext` composition; GPU Phase 1
  (offload proof, VRAM fit, chip indicator).
- **Exit:** agent scaffolds+tests+runs a small project end-to-end with
  approvals and streaming.

### Q2 (Months 4–6) — Memory & conversation
- Embeddings engine + `remember`/`recall`; workspace RAG (`ask_workspace`).
- `ask_user` interrupt tool; session persistence + resume; export.
- MemoryBrowser UI; conversation list in sidebar.
- **Exit:** agent remembers facts across sessions and answers questions
  from workspace docs.

### Q3 (Months 7–9) — Extensibility & performance
- Tool SDK + third-party tool addons; `apply_patch`, multi-file refactor.
- Optional `web_fetch`/search behind config; prompt caching & context
  management; model presets (chat vs agent vs code).
- EXE packaging decision implemented (incl. LangGraph); GPU EXE variant.
- **Exit:** a documented SDK with ≥2 third-party tools; EXE ships agent.

### Q4 (Months 10–12) — Platform & hardening
- Auto-update; local crash reports (opt-in); settings/UX polish.
- Prompt-injection audit, sandbox audit, tool fuzzing; perf pass.
- Docs refresh; v3 release.
- **Exit:** v3 with agent as flagship, CI green, installers verified.

---

## 12. Open decisions & risks

| Decision / risk | Stance |
|---|---|
| pydantic + LangGraph in the EXE (size) | include; offset with UPX/excludes — needs your sign-off |
| llama.cpp function-calling quality on 7B | keep JSON protocol; revisit with stronger default model |
| 7B capability ceiling | model presets per feature; graceful degradation everywhere |
| LangGraph API churn | pin versions; keep adapter layer thin |
| Scope discipline | Q1 is sacred: engine + graph + command tool + approvals + streaming. Everything else is later. |
| Local-only constraint | hard default; network tools opt-in with config |
