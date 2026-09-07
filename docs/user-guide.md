# User Guide

Complete guide to using **GGUF Loader** - a privacy-first desktop app that runs
one large language model fully locally: Google **Gemma 4 12B Instruct
(Q4_K_M)**. The interface is a modern React app on a FastAPI backend, and the
built-in **agent** can plan and execute multi-step file tasks inside a
workspace folder you choose.

---

## Getting Started

### 1. Launch the Application

- **Windows** - double-click `launch.bat`, then pick a mode: **1** Browser
  (default), **2** Electron desktop window, or **3** Production (built UI).
- **Linux / macOS** - run `./launch.sh` (same choices).
- **pip users** - `pip install ggufloader` then run `ggufloader`.

The launcher creates a virtualenv, installs Python and Node dependencies, and
starts everything for you. See the [Installation Guide](installation.md) for
details.

### 2. Load a Model

Loading is **automatic** - there is no manual "Load Model" step:

1. On startup the app scans the `models/` folder (plus the folder you last used)
   for the pinned file **`gemma-4-12B-it-Q4_K_M.gguf`** and loads it in the
   background.
2. The **model chip in the top-right header** shows the state:
   - `No model` - the file was not found. **Click the chip** to download the
     pinned model (progress shows right in the chip), or use the picker to
     browse to a folder that contains it.
   - a percentage while downloading - it auto-loads when finished.
   - the loaded model name once ready.

This build is pinned to Gemma 4 12B Q4_K_M: other GGUF files are rejected at
load time with a clear message.

### 3. Start Chatting

Type in the message box at the bottom and press **Enter** to send
(**Shift+Enter** for a new line). Replies stream in token by token.

- Plain **chat mode** answers questions directly.
- Press **Ctrl/Cmd + Shift + A** (or use the mode toggle) to switch to
  **Agent Mode** for file tasks.

---

## Agent Mode

Agent Mode turns the local model into a working assistant for a **workspace
folder** you choose - a project, a documentation set, any folder. Every turn
goes through a **planner**:

1. **Plan** - the planner reads your prompt and decides whether tools are
   needed. For a plain question it answers directly. For a task it writes a
   step-by-step plan and streams its reasoning live ("Planning...").
2. **Execute** - the steps run one at a time, in order: list folders, read
   files, search, create/edit/move files, run commands, use git. Each step's
   result feeds the next, and the whole process is shown **inline in the chat**
   above the reply.
3. **Answer** - the plan's final step synthesizes the results into a normal,
   clean markdown reply.

You see exactly what the agent is doing - which tool it called, what it found,
and which step it is on - like watching a human assistant work.

### Choosing a Workspace

When you enable Agent Mode you choose (or confirm) the **workspace folder**.
Every tool is sandboxed to that root: the agent can read and write files there,
but cannot touch anything outside it.

### Approvals

Some tools are sensitive and pause for an **Allow / Deny** card before they
run:

- `run_command` (shell commands)
- code execution
- git **write** operations (commits, resets, pushes)

Read-only git and all file reading/searching run freely. The run waits for your
choice - approve to continue, deny to skip that call.

### Sessions

Every conversation is a **session** (left panel: start a new one, switch, or
resume). Agent runs are checkpointed to SQLite, so a session survives app
restarts and resumes where it left off.

---

## Advanced Search (Find Paragraph)

The **Advanced Search** panel (right panel, magnifier icon) finds the passage
that answers a question - in a single file or across a folder - without any
vector database. The agent plans which files to read (read-only tools only) and
shows live progress while it scans.

---

## Right-hand Panel

The right panel hosts the app's tools. The default tabs include:

| Tab | What it does |
|---|---|
| **Files** | Browse the workspace tree, open and view files |
| **Dashboard** | Workspace overview and recent activity |
| **Templates** | Project/file templates |
| **Search** | Advanced Search - question-based passage finding |
| **Workspaces** | Manage and switch workspace folders |

Open/close the panel with **Ctrl/Cmd + Shift + ]** and jump to Files /
Dashboard / Templates with **Ctrl/Cmd + 1 / 2 / 3**.

---

## Settings

Open **Settings** (gear icon in the header). Tabs:

- **Model** - model file location and loading options, sampling defaults
- **Providers** - optional API providers alongside the local model
- **Agent** - agent preset (Research, Code Review, Refactor, Debug, ...) and
  workspace/tool permissions
- **Hardware** - GPU support (install the CUDA or Metal build, see GPU below)
- **Appearance** - dark/light theme, accent color, font size
- **Keyboard** - shortcut reference
- **Plugins** - built-in and third-party panels for the right-hand side

---

## GPU Acceleration

The app runs on CPU out of the box. For an NVIDIA GPU (Windows/Linux) or Apple
Silicon (macOS), open **Settings > Hardware** and install GPU support - it
installs the accelerated `llama-cpp-python` build with live status and asks you
to restart. The scripts `scripts/install_gpu_llama.bat` /
`install_gpu_llama.sh` do the same from the terminal.

---

## Keyboard Shortcuts

| Shortcut (Ctrl = Cmd on macOS) | Action |
|---|---|
| `Ctrl + K` | Command palette |
| `Ctrl + Shift + A` | Toggle Agent Mode |
| `Ctrl + Shift + L` | Clear chat |
| `Ctrl + Shift + [` | Show/hide left panel |
| `Ctrl + Shift + ]` | Show/hide right panel |
| `Ctrl + 1 / 2 / 3` | Right panel: Files / Dashboard / Templates |
| `Enter` | Send |
| `Shift + Enter` | New line |
| `Esc` | Stop the current reply |
| `Ctrl + /` | Keyboard shortcuts help |

---

## Tips & Best Practices

- **RAM** - Gemma 4 12B Q4_K_M needs roughly 8-10 GB free RAM to run smoothly;
  close other heavy apps while chatting.
- **Speed** - enable GPU in Settings > Hardware for the biggest speedup; on CPU
  keep the context length at the default.
- **Workspace discipline** - give the agent the smallest folder it needs; a
  huge workspace makes searches slower.
- **Privacy** - everything runs locally. Nothing you type or open leaves your
  machine unless you use a configured API provider.

---

## Troubleshooting

### Model Won't Load

- The header chip says "No model": the GGUF is not where the app looks. Click
  the chip to **download** the pinned model, or point the model picker at the
  folder containing `gemma-4-12B-it-Q4_K_M.gguf` (the default `models/` folder
  in the app directory).
- "Unsupported model": you picked a different GGUF - this build only loads the
  pinned Gemma 4 12B Q4_K_M file.

### Slow Responses

- Enable GPU in **Settings > Hardware** and restart.
- Close other RAM-heavy applications.
- Reduce the context length / generation settings in Settings > Model.

### Application Won't Start

- Check the launcher's error message (missing Python 3.10+, missing
  `python3-venv` on Debian/Ubuntu, or failed dependency install).
- Delete the virtualenv (`.venv` / `frontend/node_modules`) and re-run the
  launcher - it reinstalls everything.
- If a previous run crashed mid-write, restart the app; sessions are
  checkpointed and survive restarts.
