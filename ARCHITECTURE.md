# GGUF Loader - Architecture (current)

This document describes how GGUF Loader is structured today: a FastAPI +
React application built around **one pinned local model** (Gemma 4 12B
Instruct Q4_K_M) and a **strictly plan-driven LangGraph agent**. It is aimed
at developers who want to contribute features, add tools or presets, change
prompts/sampling, or touch the frontend.

`ARCHITECTURE_V2.md` is the separate 12-month *target* architecture; this
document describes the current build.

## Design principles

1. **A pure, testable core.** Domain logic (prompt building, plan
   execution, tools, context budgeting) lives in `ggufloader/core/` and
   imports neither FastAPI nor the UI.
2. **One model, forever.** This build is pinned to Gemma 4 12B Q4_K_M.
   Model detection, family tuning, and role matrices were removed; the load
   gate in `api/routes/model.py` rejects any other GGUF. llama.cpp is
   touched in exactly one place: `core/llm/model_backend.py`.
3. **The agent is a LangGraph graph, and it is strictly plan-driven.**
   START -> planner -> (agent <-> tools) -> END. The planner decides
   whether tools are needed and writes the step plan; the final answer
   always comes from the plan's answer step. No reactive ReAct loop.
4. **Stream everything, cancel everything.** No blocking LLM call leaves the
   user staring at a frozen UI: tokens, reasoning, plan, and tool progress
   stream over the WebSocket, and cancellation is cooperative.
5. **Safety by default.** Every tool is jailed to the workspace root;
   shell/python/git-write/move calls pause for human approval.
6. **Graceful degradation, never silent failure.** Malformed plan JSON is
   repaired and retried; an empty plan ends with an honest wrap-up; a
   refusal is never shipped when tool evidence exists - the evidence is
   rendered deterministically instead.
7. **The pinned 12B is the real user.** Prompts, schemas, retries, and
   sampling are tuned for a small quantized model that occasionally leaks
   JSON envelopes and channel markers - the pipeline cleans and repairs for
   it, and every fix is regression-tested.

## Process model

One Python process runs FastAPI. The llama.cpp runtime lives in-process
(one Llama, serialized by a lock). The React UI connects over HTTP
(/api/*) and one WebSocket (/ws) - directly to FastAPI in browser and
production mode, or via Vite's dev proxy in development. Electron
(electron/main.ts) is an optional shell: it spawns the backend itself
(port 8000) and loads the UI, cleaning both up on quit.

```
Browser / Electron shell
   |  HTTP /api/*  +  WS /ws (typed events, heartbeat)
   v
FastAPI process (uvicorn, ggufloader.api.app:create_app)
   |-- REST routers   /api/model /api/chat /api/agent /api/files /api/gpu ...
   |-- WebSocket      /ws -> ConnectionManager -> agent run orchestration
   |-- lifespan       startup: start_auto_load() scans the models folder,
   |                  background-loads the pinned GGUF
   |-- static         serves frontend/dist (production) with SPA fallback
   v
llama.cpp (core/llm/model_backend.py, the ONLY Llama) - serialized by lock
```


## Startup and model lifecycle

`api/app.py`'s lifespan calls `start_auto_load()` (api/auto_load.py), which
spawns a daemon thread that scans the default models/ folder plus the
last-used model folder for a GGUF matching the pinned Gemma 4 12B Q4_K_M
(PINNED_ARCH/PINNED_QUANT/PINNED_SIZE in config.py), loads it in the
background, and reports state through /api/model/*. When the model is
missing, the UI's model picker offers a one-click download
(PINNED_MODEL_URL) streamed by `downloadStore` with progress in the header
chip. The load path:

1. /api/model/load (or auto-load) validates the file against the pinned
   identity - other GGUFs are rejected with a clear message.
2. `core/router.py` inspects the GGUF and produces a LoadStrategy
   (n_ctx, n_gpu_layers, batch) that fits system RAM/VRAM
   (system_probe.py).
3. `core/llm/model_backend.py` instantiates the single llama_cpp.Llama.

## Agent turn flow (the heart)

An agent message arrives as {"type": "agent_start"} on /ws.
`api/websocket/handler.py` builds the callbacks, then runs
`GraphAgent.process(...)` in a thread executor. The whole turn is **one
LangGraph run**:

```
WS handler -- agent_start --> GraphAgent.process (thread)
   on_status / on_token / on_tool / on_plan / on_plan_stream / on_approval
                              |-- AgentTransport --> typed WS events
START --> planner node            (LLM: JSON plan; deltas stream as 'reasoning')
       --> agent node             (follow plan step by step)
             tool step --> tools node --> ToolOrchestrator.execute_batch
                                       (dedupe, retry, approval interrupt,
                                        stuck detection) --> back to agent
             answer step --> evidence synthesis LLM call (plain prose)
       --> END (final_answer) --> message_complete + agent_complete
```

- **Plan structure**: {goal, steps: [{step, description, tool, parameters,
  depends_on}]}. Normalized: max 6 steps, trailing answer step guaranteed.
  STEP_N.result parameter references resolve from completed steps.
- **Approval**: sensitive tools raise a LangGraph interrupt(); the UI shows
  Allow/Deny (tool_approval); the run resumes with Command(resume=...).
- **Evidence**: the answer step synthesizes from ALL completed tool steps
  (not just declared dependencies), bounded to ~6000 chars; anti-refusal
  and envelope-scrub logic guarantee clean prose.
- **Checkpointing**: SqliteSaver per workspace thread id - runs survive
  restarts and are resumable.
- **Tracing**: every node visit logs [graph] <node> enter/exit | <ms> | ...
  plus a per-turn rollup (GGUF_GRAPH_TRACE=0 to silence).

## WebSocket event vocabulary

/ws events (see api/websocket/handler.py + agent_transport.py):

| Event | Payload | Meaning |
|---|---|---|
| token | token | streamed answer text |
| reasoning | content | live planner/thinking deltas |
| agent_phase | status, phase, plan_step | coarse phase transitions |
| progress_announce | content | transient/live announcement |
| progress_step_complete | content | a plan/step line finished |
| tool_call / tool_result | call + result | tool execution feed |
| tool_approval | id, tool, args | approval request (blocks the run) |
| agent_plan_update | plan | plan object, ready |
| message_complete | content, plan, phase_log, preset, duration_ms | final message |
| agent_complete | plan, phase_log, tool_results | run finished |
| heartbeat | ts | keepalive (30 s) |
| error | message | failure |

Status strings from the agent ("Planning...", "Plan (N steps):",
"> Step N/M: ...", "[plan] -> tool(...)", "[OK] ...", ...) are mapped to
these progress events by `AgentTransport._handle_status`. That mapping is
the presentation contract - e.g. transient wait-statuses such as
"Planning..." must never become permanent timeline rows.


## Tools and safety

`core/agent/tool_registry.py` defines sandboxed tools: a Tool subclass with
name, description, JSON schema, execute(params), and an optional
requires_approval hook.

| Tool | Approval | Notes |
|---|---|---|
| list_directory, read_file, search_files, glob | never | read-only; pruned walks + caps (search/glob skip vendor dirs, read heads only) |
| write_file, edit_file, move_file | move only | mutate inside the workspace |
| run_command, run_python, git | always | shell/interpreter/git; non-mutating git reads may auto-run |

All paths resolve against the workspace root and reject escapes. Presets
(core/agent/presets.py: research, code_review, refactor, debug, full_stack,
quick_fix) whitelist/blacklist tools and set step budgets, so e.g. research
can never plan writes.

## Frontend

`frontend/src/App.tsx` renders AppLayout (Header + optional Left/Right
panels + ChatPanel + MobileNav + dialogs/banners). The WebSocket lives in
`stores/chatStore.ts`, which reduces the typed events into zustand state.
Agent runs display **inline in the chat column** (Codebuff style):
progressSteps stream while a run is live and are folded into the finished
assistant message (msg.steps) on message_complete. StreamingText renders
live tokens; a token-level filter in `agent_transport.make_token_callback`
keeps tool-call JSON envelopes out of the bubble. Right-panel agent and
workbench panels (Artifacts, Context, benchmark, plugins, ...) plug in
around the chat column. Model state (load/unload/status, download progress)
lives in modelStore + downloadStore and drives the header chip.

## Configuration

- ggufloader/config/model_families.json - the single gemma4 family:
  sampling params (official Gemma 4 guidance), the shared stable system
  prompt, context length. Read at startup by the router.
- ggufloader/config.py - pinned-model identity (PINNED_*), chat sampling
  defaults, chat max tokens, path helpers (get_paths()), per-deployment
  data directories.
- User settings are persisted by the frontend (localStorage) and sent with
  each request; sampling caps on the agent path keep structured output
  reliable on the quantized model.

## How to extend

- **Add a tool**: subclass Tool in tool_registry.py, register it in the
  default registry, give it a JSON schema (advertised automatically), set
  requires_approval if it executes anything, and add a regression test.
- **Add a preset**: add an AgentPreset entry in core/agent/presets.py
  (allowed/blocked tools, max_steps, mode text).
- **Change prompts or sampling**: family params and the system prompt live
  in model_families.json; chat defaults in config.py. The plan/answer
  prompt templates live in graph_agent.py and prompt_builder.py - keep the
  "no JSON in answers" and anti-refusal rules intact.
- **Add a REST route**: create api/routes/<name>.py and include the router
  in api/app.py under /api/<name>.
- **Add a WS event**: emit it from agent_transport.py or the handler, add a
  reducer case in chatStore.ts, and render it in the UI.
- **Frontend feature**: components in frontend/src/components/, state in a
  zustand store, typed client calls in frontend/src/api/.

## Testing and validation

- Backend: python -m pytest tests/unit - headless, no model/GPU needed.
- Frontend: cd frontend && npx tsc --noEmit and npm run build.
- Graph tracing: run with default tracing and read the [graph] lines in the
  server log to see node order and timing.
- The auto-loader is skipped under pytest (GGUFLOADER_SKIP_AUTOLOAD); for
  manual backend runs, keep the model in the models/ folder (or the
  remembered folder) and it loads itself at startup.

## Invariants

No UI/frontend code creates a second Llama | only model_backend.py touches
llama.cpp | the planner is the only gate to tool execution | the final
answer always comes from the plan's answer step | no reactive ReAct loop |
every WS event type has a matching store reducer | tools stay inside the
workspace and sensitive ones always ask first | unit tests stay headless.
