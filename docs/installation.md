# Installation Guide

How to install and launch **GGUF Loader** — a universal GGUF model loader
with a built-in plan-driven agent. Pick whichever method fits you.

> 🧪 **Note:** v2.3.0 is a testing release temporarily pinned to Gemma 4 12B
> Instruct Q4_K_M. Universal model support returns in the next release.

---

## Method 1: Prebuilt executable (easiest, end users)

1. Open the [GitHub Releases page](https://github.com/GGUFloader/gguf-loader/releases).
2. Download the artifact for your platform:
   - `GGUFLoader_v<version>_CUDA.exe` - Windows with an NVIDIA GPU (CUDA)
   - `GGUFLoader_v<version>_CPU.exe` - Windows, any machine
   - `GGUFLoader_v<version>_linux_x86_64_CPU` - Linux, CPU-only
   - `GGUFLoader_v<version>_linux_x86_64_CUDA` - Linux with NVIDIA GPU (driver ≥ 550)
3. Run it. No Python, Node, or other runtime is needed.

On first start the app looks for the pinned model and offers to download it
from the header chip if it is missing (see First Launch below).

---

## Method 2: Run from source

### Prerequisites

- **Python 3.10+** (the launchers and pip both require it)
- **Node.js 18+** (for the frontend - the launcher installs it via `npm`)
- Git (optional, to clone)

### Windows

1. Clone or download the repository.
2. Double-click **`launch.bat`**.
3. It creates a virtualenv, installs Python dependencies, installs frontend
   dependencies, then asks which mode to run:

   | Choice | Mode | Notes |
   |---|---|---|
   | **1** | Browser (default) | Backend + Vite dev server, opens in your browser |
   | **2** | Desktop | Electron native window (Electron starts its own backend on :8000) |
   | **3** | Production | Rebuilds the built UI if stale and serves it from one server |

### Linux / macOS

1. Clone or download the repository.
2. `chmod +x launch.sh`
3. Run **`./launch.sh`** - same setup and mode choices. On Debian/Ubuntu you
   may need `python3-venv` (the script tells you the exact command). The CPU
   `llama-cpp-python` wheel is installed prebuilt, so no C compiler is needed.

### Manual start (after dependencies are installed)

```bash
# backend only (development):
python -m uvicorn ggufloader.api.app:create_app --factory --port 8000

# frontend dev server (separate terminal):
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

## First Launch

1. Start the app. On startup it **auto-scans for the pinned model** - the file
   `gemma-4-12B-it-Q4_K_M.gguf` in the app's `models/` folder (plus the
   last-used model folder) - and loads it in the background.
2. If the model is not on disk, the **model chip in the header** shows a
   Download action with live progress and auto-loads the file when done.
3. Start chatting. Press **Ctrl/Cmd + Shift + A** for Agent Mode (choose a
   workspace folder to let the agent work in).

This testing release runs exactly one model — Gemma 4 12B Instruct Q4_K_M.
Other GGUF files are rejected with a clear message. The full universal model
loader (any GGUF) returns in the next release.

---

## GPU Acceleration (optional)

The default install runs on CPU. To use an NVIDIA GPU (Windows/Linux) or Apple
Silicon (macOS):

- **In the app:** open **Settings > Hardware** and follow the install flow; it
  swaps in the accelerated `llama-cpp-python` build and asks you to restart.
- **Scripts:** `scripts/install_gpu_llama.bat` (Windows) or
  `scripts/install_gpu_llama.sh` (Linux/macOS).

---

## Troubleshooting

### Python Not Found

`launch.bat` needs **Python 3.10+** on PATH - install it from python.org and
re-run. (Linux: you may also need `python3-venv` / `virtualenv`.)

### Permission Denied (Linux/macOS)

```bash
chmod +x launch.sh
```

### Frontend fails to install or build

The launcher needs **Node.js 18+** and an internet connection on first run. If
`npm install` fails, delete `frontend/node_modules` and re-run the launcher.

### Antivirus / SmartScreen warnings (Windows)

Executables built with PyInstaller are sometimes flagged. Choose "More info >
Run anyway" for the official release file, or build from source.

### Dependencies fail to install

```bash
python -m pip install -r requirements.txt   # Python deps
cd frontend && npm install                  # frontend deps
```

---

## Next Steps

See the [User Guide](user-guide.md) for the full walkthrough, or the
[FAQ](faq.md) for common questions.
