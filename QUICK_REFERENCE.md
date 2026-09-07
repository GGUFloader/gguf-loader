# GGUF Loader - Quick Reference

A privacy-first desktop app that runs one large language model - Google
**Gemma 4 12B Instruct (Q4_K_M)** - fully locally. The frontend is React +
TypeScript on a FastAPI backend, with a built-in **plan-driven agent**
(LangGraph) that can read, write, search, and run commands inside a workspace
folder you choose. No cloud, no telemetry.

---

## Install & Run

### Option 1: Prebuilt executable (recommended for end users)

Grab the right file from [GitHub Releases](https://github.com/GGUFloader/gguf-loader/releases):

| Artifact | Size | Use when |
|---|---|---|
| `GGUFLoader_v<version>_GPU.exe` | ~850 MB | Windows + NVIDIA GPU (CUDA) |
| `GGUFLoader_v<version>_CPU.exe` | ~70 MB | Windows, any machine |
| `GGUFLoader_v<version>_linux_x86_64_CPU` | ~105 MB | Linux (chmod +x, run directly) |

No Python or other runtime is needed - the exe is self-contained.

### Option 2: pip install

```bash
pip install ggufloader
ggufloader          # launch the app
```

Requires Python 3.10-3.13. The wheel only installs the `ggufloader` name, so it
is safe alongside other packages.

### Option 3: Run from source

```bash
git clone https://github.com/GGUFloader/gguf-loader.git
cd gguf-loader
python -m venv .venv
.venv\Scripts\activate        # Windows - or: source .venv/bin/activate
pip install -r requirements.txt
python -m ggufloader.main       # or: python main.py
```

### Option 4: Launcher scripts (auto-setup)

`launch.bat` (Windows) and `launch.sh` (Linux/macOS) create a virtualenv if
needed, check/install Python and Node dependencies, then ask which mode to run:

| Choice | Mode | What it does |
|---|---|---|
| **1** | Browser (default) | Starts the FastAPI backend + Vite dev server and opens the app in your browser |
| **2** | Desktop | Compiles and launches the Electron window (Electron owns the backend on :8000) |
| **3** | Production | Rebuilds `frontend/dist` if stale, then serves the built UI from one server |

The scripts report clear, actionable errors for the usual setup problems
(missing Python 3.10+, no `python3-venv`, Linux without a C compiler - the CPU
`llama-cpp-python` wheel is pulled prebuilt, so `gcc`/`cmake` are optional).

---

## First Launch

1. Start the app (any method above). On startup it **auto-detects the pinned
   Gemma 4 12B Q4_K_M GGUF** in the `models/` folder (plus the last-used model
   folder) and loads it in the background - there is no manual load step.
2. If the model file is **not on disk**, the model chip in the top-right of the
   header offers a **Download** action with live progress; once finished it
   loads automatically.
3. The header chip shows the state at a glance: `No model` / downloading with a
   percentage / the loaded filename.
4. Start chatting in the center panel. Press `Ctrl/Cmd + Shift + A` to switch
   to **Agent Mode** and pick a workspace folder.

Only the pinned model loads: any other `.gguf` file is rejected at load time
with a clear message (this build is single-model by design).

---

## Interface

- **Left panel** - chat sessions (new, switch, resume; stored in SQLite).
- **Center** - the chat. Agent turns render their **process inline**, Codebuff
  style: the plan's steps, each tool call with its result, and status lines
  appear above the final answer, which is clean markdown.
- **Right panel** - tool panels: Files, Dashboard, Templates, Advanced Search,
  Workspaces, and more (switch with the icons or `Ctrl/Cmd + 1/2/3`).
- **Header** - model chip (download/load state) and panel toggles.
- **Settings** (gear icon) - tabs: Model, Providers, Agent, Hardware,
  Appearance, Keyboard, Plugins.

### Keyboard shortcuts

| Shortcut (Ctrl = Cmd on macOS) | Action |
|---|---|
| `Ctrl + K` | Command palette |
| `Ctrl + Shift + A` | Toggle Agent Mode |
| `Ctrl + Shift + L` | Clear chat |
| `Ctrl + Shift + [` / `Ctrl + Shift + ]` | Show/hide left / right panel |
| `Ctrl + 1` / `2` / `3` | Right panel: Files / Dashboard / Templates |
| `Enter` | Send message |
| `Shift + Enter` | New line in the input |
| `Esc` | Stop the running reply |
| `Ctrl + /` | Keyboard shortcuts help |

---

## Agent Mode

Agent Mode turns the local model into a working assistant for a **workspace
folder** you choose (your project, a doc set, anything):

1. **Plan** - the planner node decides whether the request needs tools. If not,
   the model answers directly. If yes, it writes a step-by-step plan.
2. **Execute** - each step runs in order (list/read/write/edit/search files,
   run commands, git) using tools sandboxed to the workspace root.
3. **Answer** - the plan's final step synthesizes the result into a normal
   reply, shown in the chat.

Approvals: `run_command`, code execution, and git **write** operations pause for
an **Allow / Deny** card; reading/searching runs freely. Every run is
checkpointed to SQLite, so work survives restarts.

---

## GPU vs CPU

- The **GPU exe** bundles the CUDA runtime; the **CPU exe** is ~10x smaller and
  runs anywhere. CPU-only builds still work on NVIDIA machines, just slower.
- From source/pip, the default install is **CPU**. To enable GPU: open
  **Settings > Hardware** and click the GPU install option (installs the CUDA
  build with live status, then restart). macOS uses Metal.
- Manual equivalent: `scripts/install_gpu_llama.bat` / `install_gpu_llama.sh`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Header chip says "No model" | The pinned GGUF is not in the `models/` folder - click the chip to download it, or point the model picker at a folder containing `gemma-4-12B-it-Q4_K_M.gguf` |
| "Unsupported model" error | Other GGUF files are rejected by design - this build is pinned to Gemma 4 12B Q4_K_M |
| `Failed to build llama-cpp-python` on Linux | Use `launch.sh` (prebuilt CPU wheels) or install `build-essential cmake` |
| Slow responses | Close other RAM-heavy apps, or enable GPU in Settings > Hardware |
| CUDA out of memory | Lower `n_gpu_layers` / context in Settings > Model, or use the CPU build |
| Agent never reaches an answer | Check the inline timeline - if a tool call is waiting, approve or deny the card; Esc stops the run |

---

## More Docs

- [README](README.md) - full overview
- [User Guide](docs/user-guide.md) - deeper walkthrough of the UI
- [Installation](docs/installation.md) · [FAQ](docs/faq.md)
- [Documentation index](docs/DOCUMENTATION.md) · [Navigation guide](docs/NAVIGATION_GUIDE.md)
- [AGENTS.md](AGENTS.md) - codebase guide for AI coding agents
- [Architecture](ARCHITECTURE.md)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)
