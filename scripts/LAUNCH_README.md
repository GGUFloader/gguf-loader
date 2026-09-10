# GGUF Loader - Launch Scripts

This document covers the launch scripts for Windows, macOS, and Linux that live in the **project root** (`launch.bat` / `launch.sh`).

## Files

- `launch.bat` (project root) - Windows launcher
- `launch.sh` (project root) - Linux/macOS launcher

## Usage

### Windows
Double-click `launch.bat`. It creates a virtualenv if needed, installs
Python and Node dependencies, then asks which mode to run:

| Choice | Mode | What it does |
|--------|------|-------------|
| **1** | Browser (default) | Starts FastAPI backend + Vite dev server, opens in browser |
| **2** | Desktop | Compiles and launches Electron window |
| **3** | Production | Rebuilds `frontend/dist` if stale, serves built UI |

### macOS and Linux
Run the launch script from the terminal:

```bash
chmod +x launch.sh
./launch.sh
```

Same mode choices as Windows.

## Requirements

- **Python 3.10+** (the scripts check for this)
- **Node.js 18+** (installed automatically on first run via npm)
- On Debian/Ubuntu: `python3-venv` or `virtualenv` may be needed

## Troubleshooting

If you encounter issues:

1. Ensure Python 3.10+ is installed and on your PATH
2. Delete the `.venv` folder and `frontend/node_modules`, then re-run the launcher
3. On Linux, `llama-cpp-python` is pulled as a prebuilt CPU wheel — no C compiler needed