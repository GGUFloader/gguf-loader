# GGUF Loader

![GitHub License](https://img.shields.io/github/license/ggufloader/gguf-loader)
![GitHub Last Commit](https://img.shields.io/github/last-commit/ggufloader/gguf-loader)

A privacy-first, beginner-friendly desktop application for running GGUF
language models **fully locally** on Windows, Linux, and macOS. No data ever
leaves your machine.

---

## 📦 v2.2.0 — Stable Release (Universal Model Loader)

> **Install via pip:** `pip install ggufloader` then run `ggufloader`
> [View on PyPI](https://pypi.org/project/ggufloader/)

**GGUF Loader v2.2.0 is the stable, universal model loader.** You pick any
GGUF model that fits your PC's resources — from small 3B models on modest
machines to large 70B+ models on high-end rigs. The app detects your hardware
(RAM, VRAM, CPU/GPU) and recommends models that work for you.

### What v2.2.0 includes

- 🌐 **Universal model loader** — load any GGUF model, no restrictions
- 📦 **PyPI package** — `pip install ggufloader`, works in any Python environment
- 🤖 **Basic agentic mode** — LangGraph-driven agent with 7 sandboxed tools
- 🔎 **Find Paragraph** — locate a passage in a document or folder, no RAG needed
- 📂 **Full-folder summaries** — reads every readable file before answering
- ⚡ **One-click GPU** — install CUDA/Metal support from the Settings UI
- 💬 **Streaming chat** — token-by-token delivery via WebSocket
- 🔒 **100% local** — no cloud, no subscriptions, no data leaves your machine

### Install v2.2.0

**Option 1: pip**

```bash
pip install ggufloader
ggufloader
```

**Option 2: Prebuilt executable**

| Artifact | Size | Notes |
|---|---|---|
| [GGUFLoader_v2.2.0_GPU.exe](https://github.com/GGUFloader/gguf-loader/releases/download/v2.2.0/GGUFLoader_v2.2.0_GPU.exe) | ~850 MB | Windows · NVIDIA CUDA |
| [GGUFLoader_v2.2.0_CPU.exe](https://github.com/GGUFloader/gguf-loader/releases/download/v2.2.0/GGUFLoader_v2.2.0_CPU.exe) | ~70 MB | Windows · CPU-only |
| [GGUFLoader_v2.2.0_linux_x86_64_CPU](https://github.com/GGUFloader/gguf-loader/releases/download/v2.2.0/GGUFLoader_v2.2.0_linux_x86_64_CPU) | ~105 MB | Linux · CPU-only |

Click any filename above to download directly.

---

## 🧪 v2.3.0 — Testing Release (Single-Model Agent)

> ⚠️ **This is a testing/preview release.** It is locked to one model while
> we validate the new plan-driven agent architecture. Expect rough edges.
> [Report issues](https://github.com/GGUFloader/gguf-loader/issues) you find.

**v2.3.0 is a testing release** that takes the agentic experience further
with a **strictly plan-driven agent** and a **developer-style inline process
UI** — but it is temporarily pinned to a single model (Gemma 4 12B Instruct
Q4_K_M) to tune the agent's performance before expanding model support.

### What's new in v2.3.0

- 🎯 **Single-model focus (temporary)** — optimized for Gemma 4 12B Instruct
  Q4_K_M; multi-model detection removed so this one model just works. Universal
  loading returns next release.
- 📋 **Strictly plan-driven agent** — every turn goes through a planner node:
  tool-free questions answered directly; tasks get a step-by-step plan executed
  with sandboxed tools. The reactive ReAct fallback was removed.
- 🖥️ **Developer-style process UI** — plan steps, tool calls, and results
  render inline in the chat above each answer.
- 🧹 **Reliable final answers** — stray tool-call JSON and stale status text
  are scrubbed from replies.
- 📥 **Auto-load at startup** — scans `models/` folder and loads the pinned
  GGUF automatically; missing model downloads with live progress.
- 🔧 **Pruned tools** — 10 focused workspace tools (memory/meta tools removed).
- 🚀 **Self-setup launchers** — `launch.bat` / `launch.sh` handle all
  dependency installation.

### Download v2.3.0

| Artifact | Size | Notes |
|---|---|---|
| [GGUFLoader_v2.3.0_CPU.exe](https://github.com/GGUFloader/gguf-loader/releases/download/v2.3.0/GGUFLoader_v2.3.0_CPU.exe) | ~145 MB | Windows · CPU-only, works everywhere |
| [GGUFLoader_v2.3.0_CUDA.exe](https://github.com/GGUFloader/gguf-loader/releases/download/v2.3.0/GGUFLoader_v2.3.0_CUDA.exe) | ~930 MB | Windows · NVIDIA CUDA |
| [GGUFLoader_v2.3.0_linux_x86_64_CPU](https://github.com/GGUFloader/gguf-loader/releases/download/v2.3.0/GGUFLoader_v2.3.0_linux_x86_64_CPU) | ~50 MB | Linux · CPU-only |

Click any filename above to download directly. The CUDA build bundles the full
CUDA runtime; the CPU build is several times smaller.

### First launch (v2.3.0)

1. Start the app — it **auto-loads** the pinned Gemma 4 12B Q4_K_M from the
   `models/` folder in the background.
2. No model on disk? The **model chip in the header** downloads it with live
   progress and loads it when finished.
3. Chat in the main window, or press **Ctrl/Cmd + Shift + A** for Agent Mode
   and choose a workspace folder.

---

## 🔮 What's Coming Next

> **Universal Model Loader returns** — the next release removes the single-model
> restriction. You'll be able to run **any GGUF model** with the agent, with
> hardware-aware recommendations so you can pick a model that fits your PC's
> RAM/VRAM.

---

## ✨ Features

### Interface

- 🗂️ **Sessions left, chat center, tools right** — sessions (left), chat with
  inline agent process (center), tool panels (right)
- 💬 **Streaming chat** — token-by-token delivery via WebSocket
- 🤖 **Agent mode** — planner-driven runs with Allow/Deny approvals, streamed
  inline in the chat
- 📥 **Model chip** — shows load state; downloads the model with live progress
- ⚙️ **Settings** — Model, Providers, Agent, Hardware, Appearance, Keyboard,
  Plugins tabs
- 🎨 **Theme** — dark/light mode, accent colors, font size
- ⌨️ **Command palette** — Ctrl/Cmd+K, Ctrl/Cmd+Shift+A (agent mode)
- 📱 **Electron** — standalone desktop app (no browser needed)

### Core Features

- 🤖 **Plan-driven agent (LangGraph)** — a planner node decides each turn:
  tool-free questions answered directly; tasks get a step-by-step plan with
  sandboxed tools inside your workspace, with Allow/Deny approval for commands,
  code, and git writes, and SQLite checkpointing.
- 🔎 **Advanced Search (Find Paragraph)** — locate a passage in a document or
  folder with the model itself, no RAG or vector database required.
- 🧾 **Real file reading** — extracts text from `.md`, `.pdf`, `.docx`, `.txt`
  and source files.
- ⚡ **GPU acceleration** — enable under Settings → Hardware (installs CUDA/Metal
  build with live status).
- 🔒 **Privacy first** — 100% local inference. Your prompts and files never
  leave your machine.
- 💻 **Cross-platform** — Windows 10/11, Linux, and macOS (including Apple
  Silicon), via React + Electron or in the browser.

## 🎬 Screenshots

![GGUF Loader - Chat Interface](screenshots/screen1.png)

![GGUF Loader - Agent Mode](screenshots/screen2.png)

![GGUF Loader - Settings](screenshots/screen3.png)

---

## 🤖 Agentic Mode

Agentic Mode turns the local model into a working assistant for a folder you
choose. It plans multi-step tasks, calls tools, and streams every step live.

### Tools

| Tool | What it does |
|---|---|
| `list_directory` / `glob` | Explore folders and match file paths |
| `read_file` | Read any file (MD/PDF/DOCX/TXT/code) |
| `search_files` | Find files and grep for content |
| `write_file` / `edit_file` / `move_file` | Create, edit, and move files |
| `run_command` | Run a shell command (approval-gated) |
| `run_python` | Execute Python source (approval-gated) |
| `git` | Git operations (writes require approval) |

### Human approval

Shell commands, code execution, and git writes pause for an **Allow / Deny**
card. Everything else (reading, searching, file edits) runs automatically.

### Example tasks

- "Summarize the Day 4 folder" → reads all files and gives a real summary
- "Create a new feature module with proper structure"
- "Refactor this codebase and organize files"
- "Find where `MAX_TOKENS` is defined and explain it"

---

## 🔎 Advanced Search (Find Paragraph, no RAG)

Open the **Advanced Search** panel to locate a specific passage:

- **Single file** — type a question and the model finds matching paragraphs
- **Folder search** — a planner decides which files to read, with live progress
- **Smart defaults** — your last query, source, and settings are remembered

No vector database, no embeddings — just the model reading the text.

---

## ⚡ GPU Acceleration

The app runs on CPU by default. To enable GPU:

1. Open **Settings → Hardware** and click the GPU install option.
2. The app installs the CUDA-enabled build and shows a green tick when done.
3. Restart the app — inference now uses the GPU.

Manual scripts: `scripts/install_gpu_llama.bat` (Windows) /
`scripts/install_gpu_llama.sh` (Linux/macOS).

---

## 🛠️ System Requirements

- **OS:** Windows 10/11, Linux, macOS (Intel & Apple Silicon)
- **RAM:** 8 GB minimum (16 GB recommended for 12B models)
- **Storage:** ~8 GB free for the model file
- **GPU:** Optional — NVIDIA CUDA on Windows/Linux, Metal on macOS
- **Python:** 3.10–3.13 (for running from source only)

---

## 🧱 Building from source

- **Windows executable:** `scripts/build_exe.bat` — detects CUDA and names the
  output `GGUFLoader_v<version>_CUDA.exe` or `_CPU.exe` automatically.
- **Linux executable:** `scripts/build_linux.sh` — must run on Linux (or WSL);
  produces `GGUFLoader_v<version>_linux_x86_64_CPU`.
- **Tests:** `pip install pytest && python -m pytest`

## 📚 Documentation

- [Quick Reference](QUICK_REFERENCE.md)
- [Developing Addons](ggufloader/addons/README.md)
- [AGENTS.md](AGENTS.md) — codebase guide for AI coding agents
- [Architecture](ARCHITECTURE.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

MIT — see [LICENSE](LICENSE).

## 🔒 Security

Report vulnerabilities to hussainnazary475@gmail.com or see
[SECURITY.md](SECURITY.md).

## 📞 Support

- 🐛 [Report Issues](https://github.com/GGUFloader/gguf-loader/issues)
- 💬 [Discussions](https://github.com/GGUFloader/gguf-loader/discussions)
- 📧 hussainnazary475@gmail.com

---

**Built with ❤️ by the GGUF Loader community**
