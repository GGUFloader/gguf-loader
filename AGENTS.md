# AGENTS.md - Guide for AI Coding Agents

This file is a fast onboarding map for anyone (human or AI agent) modifying
the GGUF Loader codebase. It complements `ARCHITECTURE.md` (deep dive) and
`QUICK_REFERENCE.md` (user-facing quick start).

## What this project is

A **local-first desktop agent app, optimized for exactly one model: Google
Gemma 4 12B Instruct (Q4_K_M)**. It is a FastAPI + React application:

- **Backend**: Python/FastAPI (`ggufloader/api/`) - serves the REST API
  (`/api/*`), the WebSocket (`/ws`), and the built React UI. llama.cpp runs
  in-process via `llama-cpp-python`.
- **Frontend**: React + TypeScript + Tailwind (`frontend/`), streamed over a
  WebSocket. Optionally wrapped in Electron (`electron/`).
- **Agent**: a strictly **plan-driven LangGraph agent** - the planner node
  writes a step plan, then the agent node executes it step by step. There is
  **no reactive ReAct loop** and no multi-model family tuning.
- The pinned GGUF is **auto-detected and loaded at startup** from the models
  folder (or downloaded from the header chip when missing). No manual
  "Load Model" step.

Ships as a pip package (`ggufloader`), a PyInstaller one-file exe
(Windows/Linux), and from source via `launch.bat` / `launch.sh`.

## Commands

```bash
# Install (Windows dev) - venv lives in .venv
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
.venv/bin/python -m pip install -r requirements.txt           # Linux/macOS

# Backend (FastAPI) - port 8000
python -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --reload

# Frontend (Vite dev server) - port 5173, proxies /api and /ws to :8000
cd frontend && npm install && npm run dev

# Or launch everything via the launcher (mode 1 = dev/browser, 2 = Electron,
# 3 = production with a rebuilt frontend):
launch.bat                      # Windows (launch.sh on Linux/macOS)

# Backend unit tests (headless, no model/GPU needed)
.venv/Scripts/python.exe -m pytest tests/unit                 # Windows
python -m pytest tests/unit                                   # any active venv

# Frontend checks
cd frontend && npx tsc --noEmit && npm run build
```

Useful switches: `GGUF_GRAPH_TRACE=0` disables per-node graph tracing;
`GGUFLOADER_SKIP_AUTOLOAD=1` skips the startup model scan (the auto-loader
is already a no-op under pytest).


## Layout

```
launch.bat / launch.sh          launcher: venv setup + 3 launch modes
main.py                         thin bootstrap (uvicorn factory import)
ggufloader/                     THE backend package - all Python lives here
  _version.py                   single source of truth for the version
  config.py                     constants: pinned-model identity, chat sampling, paths
  config/model_families.json    ONE family: gemma4 (params + system prompt)
  api/
    app.py                      FastAPI factory: CORS, route mounting, /ws,
                                static dist serving, lifespan (auto-load)
    auto_load.py                startup scan/load of the pinned GGUF + download helper
    deps.py                     dependency access (model backend etc.)
    routes/                     REST routers: model, chat, agent, files, gpu, ...
    websocket/handler.py        /ws endpoint: ConnectionManager + agent orchestration
  core/
    llm/model_backend.py        the ONLY module that instantiates llama_cpp.Llama
    llm/prompt_builder.py       conversation + final-response prompt formatting
    router.py                   inspect GGUF -> LoadStrategy (n_ctx, gpu layers, batch)
    system_probe.py             RAM/VRAM probing, GPU offload support
    agent/
      graph_agent.py            LangGraph agent: planner/agent/tools nodes (THE agent)
      tool_registry.py          Tool base + sandboxed tools (read/write/search/glob/shell/git)
      tool_orchestrator.py      executes tool batches: dedupe, retry, approval, stuck detection
      agent_transport.py        status strings -> typed WS progress events
      presets.py                agent presets (research/code_review/refactor/debug/...)
      token_cleaner.py          Gemma channel-token cleaning
      context_budget.py         context budgeting + compaction
  services/ ui/ widgets/        legacy Qt-era code still present, NOT the UI path
frontend/                       React + TypeScript + Tailwind app
  src/App.tsx                   <AppLayout/> root
  src/components/               layout, chat, agent, model, settings, workbench, ui
  src/stores/                   zustand stores (chatStore = WS reducer, modelStore, ...)
  src/api/                      typed REST + WS client
  dist/                         production build served by FastAPI
electron/                       optional Electron shell (spawns backend + loads UI)
tests/unit/                     pytest suite (headless)
```

The legacy PySide6 UI (`python main.py --qt`) is deprecated and no longer
ships in the installer or dependencies - the React app running in Electron
is the only UI, and the backend boots without PySide6. Build features in
frontend/ and ggufloader/api.

## Non-negotiable conventions

1. **One model, one runtime.** This build loads exactly Gemma 4 12B Q4_K_M;
   `api/routes/model.py` rejects other GGUFs. Only
   `ggufloader/core/llm/model_backend.py` may instantiate `llama_cpp`.
   One model at a time, serialized - never create a second `Llama`.
2. **The agent is strictly plan-driven.**
   `START -> planner -> (agent <-> tools) -> END`. The planner decides
   whether tools are needed and writes the plan; the agent node never
   invents its own action loop. The final answer always comes from the
   plan's answer step. Do not reintroduce a reactive ReAct fallback -
   tests enforce plan mode.
3. **WebSocket events are the UI contract.** The typed event vocabulary
   (`token`, `reasoning`, `progress_*`, `tool_*`, `message_complete`, ...)
   is consumed by `frontend/src/stores/chatStore.ts`. Add fields; never
   silently rename or remove types without updating the reducer.
4. **Everything lives under `ggufloader/`.** No new top-level modules -
   the wheel claims only the `ggufloader` name.
5. **Version**: bump `ggufloader/_version.py` and `pyproject.toml` together;
   update `CHANGELOG.md`; tag `v<version>` to trigger the release workflow
   (`.github/workflows/build-release.yml`).
6. **Tests are headless.** Never require a loaded model/GPU in unit tests.
   New graph/tool/transport behavior needs a regression test in `tests/unit`.
7. **Line endings**: on Windows the repo normalizes to CRLF on checkout
   (git autocrlf). `git diff` warnings about LF -> CRLF on edited files are
   normal - don't fight them, and don't convert whole files' endings.
8. **Tools stay sandboxed.** Every tool resolves paths against the workspace
   root and rejects escapes. `run_command`, `run_python`, mutating `git`
   calls, and `move_file` always require human approval; reads never do.


## The agent (deep dive)

`ggufloader/core/agent/graph_agent.py` builds a small LangGraph `StateGraph`
with three traced nodes:

```
START -> planner -> agent -> (continue: tools -> agent | end: END)
                       ^------------------------------+
```

- **planner node** (`_planner_node`) - the FIRST node of every run. It calls
  the LLM for a JSON plan ({"goal", "steps": [...]}), retrying malformed
  JSON with a repair hint (the planner is the only gate to tool execution).
  Plans are normalized: capped at 6 steps and guaranteed to end with an
  answer step (tool: null) when the model produced only tool steps.
  Planner deltas stream to the UI as `reasoning` events.
- **agent node** (`_agent_node`) - strictly follows the plan one step at a
  time (`_follow_plan_step`):
  - Tool steps produce `pending_calls`, which the tools node executes.
    STEP_N.result references in parameters resolve from earlier steps.
  - Answer steps collect evidence from ALL completed plan steps (bounded,
    ~6000 chars) and ask the LLM to synthesize plain prose. Answers are
    scrubbed (`strip_tool_envelope`) and never ship an access-refusal when
    tool evidence exists - the evidence is rendered deterministically.
  - When the planner produced nothing, the run ends with an honest wrap-up.
    There is no reactive fallback.
- **tools node** (`_tools_node`) - executes the pending batch through
  `ToolOrchestrator.execute_batch`: dedupes already-executed call
  signatures, retries failed calls once with a repair hint, honors approval
  (graph interrupt() -> Allow/Deny -> Command(resume=...)), and reports
  results back into the plan step.
- **router** - `continue` while calls remain and the step budget allows,
  `end` once a final answer exists.

State is checkpointed to SQLite (SqliteSaver, one file per workspace
thread) so conversations resume across restarts. Cancellation is
cooperative (`cancel()` sets an event the nodes check). Graph tracing logs
`[graph] <node> enter/exit | <ms> | <summary>` per node plus a `turn done`
rollup - the fastest way to see architecture issues (disable with
`GGUF_GRAPH_TRACE=0`).

Sampling: chat defaults live in `config.py` (CHAT_TEMPERATURE=0.2,
CHAT_TOP_K=80, CHAT_REPEAT_PENALTY=1.05) and the family params follow
official Gemma 4 guidance; the agent path caps temperature/top_k for
reliable structured output.

## Frontend wiring (short version)

`frontend/src/stores/chatStore.ts` owns the WebSocket connection
(`connectWebSocket()`), a zustand reducer over the WS events, and the
message list. Agent runs render **inline in the chat column** (Codebuff
style): progress steps are folded into the finished assistant message on
`message_complete`. Key stores: `modelStore` (load/unload/status),
`downloadStore` (pinned-model download with header-chip progress),
`uiStore`, `themeStore`, `workspaceStore`. The header shows the loaded
model chip plus the version banner; a first-launch compatibility dialog
confirms the pinned model is present.

## Session workflow for coding agents

The repo keeps light session artifacts (`feature_list.json`, `progress.md`,
`session-handoff.md`, `init.sh`) used by the agent harness workflow: start
by reading `feature_list.json` and `progress.md`; work on one feature;
verify with `python -m pytest tests/unit -x -q`; update the artifacts at
the end of the session. Follow the conventions above even when the harness
is inactive - they encode hard-won constraints (single model, plan-driven
agent, event contract, headless tests).

## Docs index

- `README.md` - user install guide | `QUICK_REFERENCE.md` - user quick start
- `ARCHITECTURE.md` - this codebase's architecture (current) |
  `ARCHITECTURE_V2.md` - 12-month target architecture
- `CHANGELOG.md` - history | `CONTRIBUTING.md` - contribution guide
