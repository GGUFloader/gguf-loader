# AGENTS.md — Guide for AI Coding Agents

This file is a fast onboarding map for anyone (human or AI agent) modifying the
GGUF Loader codebase. It complements `ARCHITECTURE.md` (deep dive) and
`QUICK_REFERENCE.md` (user-facing quick start).

## What this project is

A **PySide6 (Qt) desktop app** that runs **GGUF LLMs locally** via
`llama-cpp-python` (llama.cpp). Features: chat panel, always-on-top Floating
Chat addon, agentic mode (LangGraph agent with approval-gated tools), and
"Find Paragraph" folder search. Ships as a pip package (`ggufloader`), a
PyInstaller one-file exe (Windows/Linux), and a wheel/sdist.

## Commands

```bash
# Install (Windows dev)
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# Run
python main.py            # or launch.bat / launch.sh (auto-setup)

# Test (unit tests, no model/GPU needed)
python -m pytest tests/unit

# Build executables
scripts/build_exe.bat     # Windows → dist/GGUFLoader_v<ver>_<GPU|CPU>.exe
scripts/build_linux.sh    # Linux/WSL → dist/GGUFLoader_v<ver>_linux_x86_64_CPU
python -m PyInstaller build_exe.spec
```

## Layout

```
main.py                    # repo-root entry (thin bootstrap; app logic in ggufloader/)
ggufloader/                # THE app package — everything lives here
  _version.py              # single source of truth for the version (mirrored in pyproject.toml)
  main.py                  # QApplication bootstrap + DLL path setup
  resource_manager.py      # resolves per-deployment paths (repo / pip / frozen exe)
  addon_manager.py         # loads addons (see ggufloader/addons/README.md)
  config.py  utils.py
  ui/                      # main_window, sidebar, chat_panel, agent_panel, find_dialog, theme
  widgets/                 # chat_bubble, feedback_dialog
  core/
    llm/model_backend.py   # the ONLY module that instantiates llama_cpp.Llama
    engine/                # ModelEngine protocol, LlamaCppEngine, LangChain adapter
    agent/                 # LangGraph agent loop, tool registry, text extraction
    search/                # Find Paragraph: paragraph_search, planner
  services/                # Qt worker-thread services (model, chat, agent, search, gpu install, launcher)
  addons/                  # bundled addons (floating_chat) + addon dev guide
scripts/                   # build/install helpers (bat + sh)
build_hooks/               # PyInstaller hooks incl. llama_cpp DLL collection
tests/unit/                # pytest suite (headless)
```

## Non-negotiable conventions

1. **llama.cpp is touched in exactly one place.** Only
   `ggufloader/core/llm/model_backend.py` may import/instantiate `llama_cpp`
   (and `core/engine/llama_cpp_engine.py` wraps it). Everything else — UI,
   agents, services, addons — must go through the engine/backend. The runtime
   is **one model at a time, serialized**; never create a second `Llama`.
2. **Qt lives on the main thread.** Background work (model calls, file I/O,
   installs) runs in `QThread` workers under `ggufloader/services/` with
   signals for progress/completion. Don't block the UI thread.
3. **Lazy imports for testability.** Modules that `import llama_cpp` or
   PySide6 do so inside functions, so unit tests (headless, no model) can
   import the logic without pulling in the runtime.
4. **Everything lives under `ggufloader`.** No new top-level modules in
   site-packages — the wheel must only claim the `ggufloader` name.
5. **Version**: update `ggufloader/_version.py` (and `pyproject.toml`) when
   releasing; tag `v<version>` to trigger the release workflow.
6. **Addons**: see `ggufloader/addons/README.md` — contract is a package with
   `register(parent=None) -> QWidget`.
7. **Executable naming**: builds are versioned + variant-labeled
   (`GGUFLoader_v<ver>_GPU.exe` / `_CPU.exe` / `_linux_x86_64_CPU`). The
   Windows build script auto-detects GPU vs CPU from the installed wheel.
8. **Linux llama-cpp-python**: no PyPI wheel exists for Linux — `pip install`
   compiles from source (needs gcc/cmake), unless installed from abetlen's
   prebuilt index (`--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`).
   `launch.sh` uses that index automatically when build tools are missing.

## Agent & GPU support (v2.2.0)

**Agent Mode is a LangGraph StateGraph** — `ggufloader/core/agent/graph_agent.py`:

- Graph: `START → agent → (continue: tools → agent | end: END)`. The `agent`
  node asks the LLM for the next JSON action (schemas + few-shot, with
  malformed-JSON repair), the `tools` node executes calls (one corrective
  retry per failure), and `_router` continues while work remains. A step
  budget (`max_steps`) caps each run; the final answer streams tokens.
- **Checkpointing**: `langgraph.checkpoint.sqlite.SqliteSaver` — one SQLite
  DB per thread. The thread id is derived from the workspace path
  (`agent-<sha>`), so the same folder resumes the same conversation across
  app restarts.
- **Approval**: sensitive tools (shell, git) suspend the graph via LangGraph
  `interrupt()`; the UI shows Allow/Deny and resumes with
  `Command(resume=...)`.
- **Cancellation is cooperative** — `cancel()` sets an event the nodes check
  between LLM and tool calls.
- `process()` keeps the old `AgentEngine` call signature, so the service/UI
  layer can swap engines without changes.

**One-click GPU install** — `ggufloader/services/gpu_install_service.py`:

- `GpuInstallService` (QThread worker) runs the platform installer via
  `launcher_service` (`install_gpu_llama.bat` / `.sh`) and emits
  `done(success, message)`.
- The sidebar button (`ui/sidebar_panel.py`, "⬇ Install GPU Support") calls
  `main_window._install_gpu_support()`; state comes from
  `is_gpu_support_installed()` and the button flips to "✅ GPU Support
  Installed" (green tick) when the CUDA build is present.
- Installing GPU support swaps the llama-cpp-python wheel for the CUDA build
  (abetlen cu124 index). Rebuild the exe with `scripts/install_gpu_llama.bat`
  followed by `build_exe.bat` to produce the `_GPU.exe` variant.

## Release flow

1. Bump `_version.py` + `pyproject.toml`; move CHANGELOG `[Unreleased]` →
   `[<version>]`.
2. Commit, push `main`, tag `v<version>`, push the tag.
3. `.github/workflows/build-release.yml` builds Windows (CPU) + Linux artifacts
   and publishes a GitHub Release. The GPU exe is built locally only (CI is
   CPU-only) — attach `dist/GGUFLoader_v<ver>_GPU.exe` manually.

## Docs index

- `README.md` — user install guide · `QUICK_REFERENCE.md` — user quick start
- `ARCHITECTURE.md` / `ARCHITECTURE_V2.md` — deep architecture
- `ggufloader/addons/README.md` — addon development
- `CHANGELOG.md` — history · `CONTRIBUTING.md` — contribution guide
