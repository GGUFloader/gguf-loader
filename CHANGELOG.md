# Changelog

All notable changes to GGUF Loader will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2026-08-11

### Added

- **LangGraph-powered Agent Mode**: the agent loop was rebuilt on
  LangGraph's `StateGraph` (`START → agent → tools → agent → … → END` with
  conditional routing), replacing the older hand-rolled loop. The graph
  supports streaming, checkpointed execution, and resumption from arbitrary
  points.
- **Resumable agent conversations**: Agent Mode now persists each
  conversation in SQLite via LangGraph's `SqliteSaver`, keyed by a stable
  per-workspace thread id — the same folder resumes the same conversation
  thread even after the app restarts.
- **Approval-before-execution for sensitive tools**: shell commands and
  git-write tools suspend the run through LangGraph `interrupt()` *before*
  anything executes, surface an approval prompt to the user, and resume from
  the exact interrupt point with the decision — no partial results lost.
- **Malformed-JSON auto-repair**: if the model returns broken action JSON,
  the agent asks it to fix the payload (with retries) instead of failing.
- **Corrective tool retries**: failed tool calls get a corrective retry;
  calls that keep failing are skipped rather than repeated endlessly.
- **Streamed final answers**: the agent's final response streams token by
  token through the app's streaming callbacks.
- **Cooperative cancellation**: a cancel request is honoured between steps,
  so long-running agent turns stop promptly instead of draining the step
  budget.
- **PyPI distribution** (`pyproject.toml`): `pip install ggufloader` installs
  the app; launch with the `ggufloader` command. Ships the flat-layout app
  modules plus a `ggufloader` compat package (icons included as package data).
- **Installed-package mode** in the resource manager: data/config/cache/logs
  now live in the per-user data dir instead of site-packages when running
  from a pip install, and deployment detection no longer mistakes the repo
  checkout for an installed copy.
- **GPU & CPU executable variants**: releases now ship both a CUDA-enabled
  `GGUFLoader_v<version>_GPU.exe` (~850 MB) and a CPU-only
  `GGUFLoader_v<version>_CPU.exe` (~70 MB); Linux binaries are named
  `GGUFLoader_v<version>_linux_x86_64_CPU`. `scripts/build_exe.bat` detects
  the installed llama-cpp-python build and names the output automatically, and
  the build scripts keep previously built artifacts instead of wiping `dist/`.
- **Hardened launchers** (`launch.sh`): clear, actionable preflight errors
  when Python 3.10+ is missing, `python3-venv` is absent (falls back to
  `virtualenv`), PyPI is unreachable, or the Linux C toolchain is missing — in
  which case llama-cpp-python is installed from abetlen's prebuilt CPU wheel
  index instead of failing a source build.

### Changed

- **Agent Mode enhancements**: richer agent engine with plan
  announcements before multi-tool turns, step progress reporting, a step
  budget with guarded cancellation, one corrective retry per failed tool
  call, and coverage directives that push the model to answer fully when it
  stops early.
- **Find Paragraph folder scans are much faster**: directory traversal now
  prunes build/dependency dirs (`.venv`, `node_modules`, `.git`, ...) as it
  walks instead of scanning the whole tree first, and hit dedup normalizes
  each quote once instead of re-running a regex on every comparison — ~40x
  faster on a repo-sized workspace with identical results.

### Fixed

- **Collision-proof pip installs**: the whole app now ships inside a single
  `ggufloader` package (previously the wheel installed top-level `config`,
  `utils`, `main`, `ui`, `core`, `services`, `widgets`, `addons` modules into
  site-packages, which could silently break - or be broken by - another
  package in a shared/global environment). `pip install ggufloader` now claims
  only the `ggufloader` name; the app imports are `ggufloader.xxx`.

---

## [2.1.2] - 2026-08-07

### Fixed
- Floating chat button no longer disappears when switching apps on macOS (the `Tool`
  window flag is now dropped on macOS so the button stays visible over other apps)
- Floating chat button can no longer get stuck minimized (it auto-restores, and
  clicking the button restores a minimized chat window instead of hiding it)
- Floating chat button and chat window now clamp to the **available** screen area,
  so they stay clear of taskbars, docks, and menu bars on all OSes
- Chat window no longer offers a minimize button (a minimized companion window was
  a trap state that couldn't be reliably restored)

### Docs
- Documented the Linux Wayland limitation (button stays inside the app window;
  run under X11 / `QT_QPA_PLATFORM=xcb` for full floating behavior)
- Added Linux build script (`scripts/build_linux.sh`) and GitHub Actions workflow
  that build and attach Windows + Linux installers to releases

---

## [2.1.0] - 2026-01-23

### Added
- Floating Chat addon with cross-platform support (Windows, Linux, macOS)
- Draggable floating button that stays on top of all windows
- Custom icon support for floating chat button (`float.png`)
- Chat window with modern UI and message history
- Position persistence for floating button between sessions
- Smooth animations and hover effects for floating button
- Keyboard shortcuts (Ctrl+Enter to send messages)
- Status widget for addon management in sidebar

### Fixed
- Floating chat button icon (`float.png`) now included in executable builds
- Floating chat button displays custom icon correctly in built executables
- Cross-platform window management for Linux (X11) and macOS
- Resource path handling for packaged executables

### Changed
- Enhanced addon system with better lifecycle management
- Improved resource manager for icon and asset discovery

---

## [2.0.1] - 2024-01-XX

### Added
- Smart Floating Assistant addon pre-installed
- Addon system with extensible architecture
- Modern PySide6-based UI
- Resource manager for better path handling
- Comprehensive documentation in `/docs` folder

### Fixed
- Resolved all import issues for seamless execution
- Fixed relative import problems
- Resolved addon detection issues
- Improved resource path handling in packaged executables
- Better error messages and logging

### Changed
- Improved stability with better error handling
- Enhanced resource management
- Single executable file distribution (no Python installation required)

---

## [2.0.0] - 2024-XX-XX

### Added
- Complete rewrite with modular architecture
- Mixin-based design pattern for better code organization
- Addon system support
- Floating Chat addon with cross-platform compatibility
- Chat bubble widget for better message display
- Collapsible widget for UI organization
- Feedback system with configurable endpoints
- Export functionality for chat conversations
- Status indicators for model loading and generation

### Changed
- Migrated from PyQt to PySide6
- Restructured codebase into logical modules (models, ui, widgets, mixins)
- Improved chat interface with HTML formatting
- Enhanced model loading with better error handling

### Removed
- Legacy monolithic code structure

---

## [1.x.x] - Previous Versions

### Features
- Basic GGUF model loading
- Simple chat interface
- Model parameter configuration
- Chat history management

---

## Version Naming Convention

- **Major version (X.0.0)**: Breaking changes, major feature additions
- **Minor version (0.X.0)**: New features, non-breaking changes
- **Patch version (0.0.X)**: Bug fixes, minor improvements

## Categories

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes

---

## How to Update

### For Users
1. Download the latest `.exe` file from [Releases](https://github.com/yourusername/gguf-loader/releases)
2. Replace your old executable
3. Your settings and chat history are preserved

### For Developers
```bash
git pull origin main
pip install -r requirements.txt --upgrade
python gguf_loader_main.py
```

---

## Support

- **Report Issues**: [GitHub Issues](https://github.com/yourusername/gguf-loader/issues)
- **Documentation**: See `/docs` folder
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)

---

[Unreleased]: https://github.com/GGUFloader/gguf-loader/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/GGUFloader/gguf-loader/compare/v2.1.2...v2.2.0
[2.1.2]: https://github.com/GGUFloader/gguf-loader/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/GGUFloader/gguf-loader/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/GGUFloader/gguf-loader/compare/v2.0.1...v2.1.0
[2.0.1]: https://github.com/yourusername/gguf-loader/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/yourusername/gguf-loader/releases/tag/v2.0.0
