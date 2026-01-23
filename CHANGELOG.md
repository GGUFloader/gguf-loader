# Changelog

All notable changes to GGUF Loader will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/yourusername/gguf-loader/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/yourusername/gguf-loader/compare/v2.0.1...v2.1.0
[2.0.1]: https://github.com/yourusername/gguf-loader/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/yourusername/gguf-loader/releases/tag/v2.0.0
