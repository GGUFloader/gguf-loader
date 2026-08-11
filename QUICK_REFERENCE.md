# GGUF Loader — Quick Reference

A privacy-first desktop app that runs **GGUF large language models locally** on
Windows, Linux, and macOS (PySide6 + llama.cpp via `llama-cpp-python`). Load a
`.gguf` model, chat with it, and use the floating chat and agentic modes —
everything runs on your machine, no cloud.

---

## Install & Run

### Option 1: Prebuilt executable (recommended for end users)

Grab the right file from [GitHub Releases](https://github.com/GGUFloader/gguf-loader/releases):

| Artifact | Size | Use when |
|---|---|---|
| `GGUFLoader_v<version>_GPU.exe` | ~850 MB | Windows + NVIDIA GPU (CUDA) |
| `GGUFLoader_v<version>_CPU.exe` | ~70 MB | Windows, any machine |
| `GGUFLoader_v<version>_linux_x86_64_CPU` | ~105 MB | Linux (chmod +x, run directly) |

No Python or other runtime is needed — the exe is self-contained.

### Option 2: pip install

```bash
pip install ggufloader
ggufloader          # launch the app
```

Requires Python 3.10–3.13. The wheel only installs the `ggufloader` name, so it
is safe alongside other packages.

### Option 3: Run from source

```bash
git clone https://github.com/GGUFloader/gguf-loader.git
cd gguf-loader
python -m venv .venv
.venv\Scripts\activate        # Windows — or: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Option 4: Launcher scripts (auto-setup)

`launch.bat` (Windows) and `launch.sh` (Linux/macOS) create a virtualenv if
needed, check/install dependencies, and start the app. They report clear,
actionable errors for the usual setup problems:

- **Linux without a C compiler** — no problem: `llama-cpp-python` is installed
  from abetlen's **prebuilt CPU wheel index** instead of being compiled, so
  `gcc`/`cmake` are optional.
- Missing `python3-venv` (Debian/Ubuntu) — falls back to `virtualenv`, or tells
  you the exact `apt` command.
- Python < 3.10, no network to PyPI, or a broken venv — each gets a specific
  message with the fix.

---

## First Launch

1. **Get a model** — browse GGUF models on
   [Hugging Face](https://huggingface.co/models?library=gguf) (e.g. Mistral,
   Llama, DeepSeek, Qwen).
2. Click **Load Model**, pick your `.gguf` file, wait for it to load.
3. Chat in the main panel, or click the **floating chat button** for a
   desktop-level chat window.

---

## Features

- **Chat panel** — streamed responses from the loaded local model.
- **Floating Chat addon** — always-on-top messenger-style button; drag it
  anywhere, position is remembered. (On Linux Wayland it stays inside the app
  window — use X11 / `QT_QPA_PLATFORM=xcb` for full floating behavior.)
- **Agentic Mode** — LangGraph-driven working assistant for a folder you
  choose: it plans multi-step tasks, reads/creates/edits files via tools, and
  streams every step. Approval-gated tools keep it safe, and each workspace's
  conversation is checkpointed to SQLite — it survives app restarts and
  resumes where you left off.
- **Find Paragraph** — locate the passage that answers a question inside a
  document or a whole folder (light mode pre-filters by keyword; "exhaustive"
  scans everything). No embeddings or vector store needed.

## GPU vs CPU

- The **GPU exe** bundles the CUDA runtime; the **CPU exe** is ~10x smaller and
  runs anywhere. CPU-only builds still work on NVIDIA machines, just slower.
- From source/pip, the default install is **CPU**. To enable GPU on Windows:
  click **⬇ Install GPU Support** in the app's sidebar — it installs the CUDA
  build with a live status and flips to a green ✅ when done (then restart).
  Equivalent manual path: `scripts/install_gpu_llama.bat`. macOS uses Metal
  (built via `CMAKE_ARGS="-DGGML_METAL=on"`). CUDA wheels come from
  `https://abetlen.github.io/llama-cpp-python/whl/cu124`.

---

## Addons

Addons are small packages that plug into the app UI. The **Floating Chat**
addon ships bundled. Each addon is a directory with an `__init__.py` exposing a
`register(parent=None) -> QWidget` function; the returned widget is hosted in
the sidebar and in an "Addon:" dialog.

- Where addons live: bundled ones in `ggufloader/addons/`; user addons in the
  per-user data directory resolved by `find_addons_dir()`.
- Write your own: see **[Developing Addons](ggufloader/addons/README.md)**.

---

## Development

```bash
# Tests (no GPU/model needed)
python -m pytest tests/unit

# Windows executable — detects GPU vs CPU and names the artifact
scripts/build_exe.bat                 # → dist/GGUFLoader_v<ver>_GPU.exe | _CPU.exe

# Linux executable (run on Linux or WSL)
scripts/build_linux.sh                # → dist/GGUFLoader_v<ver>_linux_x86_64_CPU

# Wheel / sdist
pip install build && python -m build  # → dist/
```

- Version lives in `ggufloader/_version.py` (mirrored in `pyproject.toml`).
- One-file binaries are **not** cross-platform — build each on its own OS.
- New bundled addons must be added to `build_exe.spec` (datas + hiddenimports).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Chat says "Model: Not loaded" | Load a model in the main window first |
| `Failed to build llama-cpp-python` on Linux | Use `launch.sh` (prebuilt CPU wheels) or install `build-essential cmake` |
| Floating button stuck / off-screen | Delete the `FloatingChat` settings (registry / `~/.config/GGUFLoader/…` / macOS plist) and restart |
| Button doesn't float above apps on Linux | That's Wayland — run under X11 or `QT_QPA_PLATFORM=xcb` |
| CUDA out of memory | Use a smaller model, fewer context layers (`n_gpu_layers`), or the CPU build |
| Slow folder search | Use light mode (default) — it only reads keyword-matching chunks |

---

## More Docs

- [README](README.md) — full overview and install guide
- [Developing Addons](ggufloader/addons/README.md) — addon API and examples
- [AGENTS.md](AGENTS.md) — codebase guide for AI coding agents
- [Architecture](ARCHITECTURE.md) / [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)
