# Package Structure

This document explains the structure of the GGUF Loader 2.0.0 PyPI package and how the Smart Floating Assistant addon is included.

## 📦 Package Overview

**Package Name**: `ggufloader`  
**Version**: `2.0.0`  
**Command**: `ggufloader`  

When users install with `pip install ggufloader`, they get:
- Complete GGUF Loader application
- Smart Floating Assistant addon (pre-installed)
- Comprehensive documentation
- All necessary dependencies

## 🏗️ Directory Structure

```
ggufloader/
├── pyproject.toml              # Package configuration
├── README_PYPI.md             # PyPI package description
├── build_pypi.py              # Build script for PyPI
├── requirements.txt           # Dependencies
├── 
├── # Main Application Files
├── main.py                    # Application entry point
├── addon_manager.py           # Addon management system
├── config.py                  # Configuration
├── utils.py                   # Utilities
├── icon.ico                   # Application icon
├── 
├── # UI Components
├── ui/
│   ├── ai_chat_window.py      # Main chat interface
│   └── apply_style.py         # UI styling
├── 
├── # Core Models
├── models/
│   ├── model_loader.py        # GGUF model loading
│   └── chat_generator.py      # Text generation
├── 
├── # UI Mixins
├── mixins/
│   ├── ui_setup_mixin.py      # UI setup
│   ├── model_handler_mixin.py # Model handling
│   ├── chat_handler_mixin.py  # Chat functionality
│   ├── event_handler_mixin.py # Event handling
│   └── utils_mixin.py         # Utility functions
├── 
├── # Widgets
├── widgets/
│   └── chat_bubble.py         # Chat bubble component
├── 
├── # Pre-installed Addons
├── addons/
│   └── smart_floater/         # Smart Floating Assistant
│       ├── __init__.py        # Addon entry point
│       ├── simple_main.py     # Main addon logic
│       ├── main.py            # Full-featured version
│       ├── floater_ui.py      # UI components
│       ├── comment_engine.py  # Text processing
│       ├── injector.py        # Text injection
│       ├── error_handler.py   # Error handling
│       ├── privacy_security.py # Privacy features
│       └── performance_optimizer.py # Performance
├── 
└── # Documentation
    └── docs/
        ├── README.md              # Documentation index
        ├── installation.md        # Installation guide
        ├── quick-start.md         # Quick start guide
        ├── user-guide.md          # Complete user manual
        ├── addon-development.md   # Addon development guide
        ├── addon-api.md           # API reference
        ├── smart-floater-example.md # Example addon
        ├── configuration.md       # Configuration guide
        ├── troubleshooting.md     # Troubleshooting
        ├── contributing.md        # Contributing guide
        └── package-structure.md   # This file
```

## 🚀 Installation and Usage

### Installation
```bash
pip install ggufloader
```

### Launch Application
```bash
ggufloader
```

This command launches `main.py` which includes:
- Full GGUF Loader functionality
- Smart Floating Assistant addon (automatically loaded)
- Addon management system
- All UI components

## 🔧 How Addons Are Included

### Addon Discovery
When GGUF Loader starts, the `AddonManager` automatically:

1. **Scans** the `addons/` directory
2. **Finds** folders with `__init__.py` files
3. **Loads** addons by calling their `register()` function
4. **Registers** an entry for each addon in the **Addons** menu

### Smart Floater Integration
The Smart Floating Assistant is included as a pre-installed addon:

```python
# addons/smart_floater/__init__.py
from .simple_main import register
__all__ = ["register"]

# When loaded, it provides:
# - Global text selection detection
# - Floating button interface  
# - AI text processing (summarize/comment)
# - Seamless clipboard integration
```

### Addon Lifecycle
1. **Package Installation**: Addon files are installed with the package
2. **Application Start**: `AddonManager` discovers and loads addons
3. **User Interaction**: Users launch addons from the **Addons** menu
4. **Background Operation**: Smart Floater runs continuously in background

## 📋 Package Configuration

### pyproject.toml Key Sections

```toml
[project]
name = "ggufloader"
version = "2.0.0"
dependencies = [
    "llama-cpp-python>=0.3.13",
    "PySide6>=6.6.1", 
    "pyautogui>=0.9.54",
    "pyperclip>=1.8.2",
    "pywin32>=306; sys_platform == 'win32'",
]

[project.scripts]
ggufloader = "gguf_loader.gguf_loader_main:main"

[tool.setuptools]
packages = [
    "gguf_loader", 
    "gguf_loader.addons", 
    "gguf_loader.addons.smart_floater"
]
include-package-data = true
```

### Package Data Inclusion
All necessary files are included:
- Python source code
- Documentation (`.md` files)
- Icons and images
- Configuration files
- Addon files

## 🎯 User Experience

### First-Time Users
1. **Install**: `pip install ggufloader`
2. **Launch**: `ggufloader`
3. **Load Model**: Click "Select GGUF Model"
4. **Use Smart Floater**: Select text anywhere → click ✨ button

### Addon Discovery
- Smart Floater appears in the **Addons** menu automatically
- Users can click to open control panel
- No additional installation required
- Works immediately after model loading

### Documentation Access
Users can access documentation:
- Online: GitHub repository
- Locally: Installed with package in `docs/` folder
- In-app: Help links and tooltips

## 🔄 Version Updates

### Updating the Package
When releasing new versions:

1. **Update version** in `pyproject.toml`
2. **Update changelog** and documentation
3. **Test addon compatibility**
4. **Build and upload** to PyPI

### Addon Updates
Smart Floater updates are included in package updates:
- Bug fixes and improvements
- New features and capabilities
- Performance optimizations
- Security enhancements

## 🛠️ Development Workflow

### For Package Maintainers
1. **Develop** new features and addons
2. **Test** thoroughly with various models
3. **Update** documentation
4. **Build** package with `python build_pypi.py`
5. **Upload** to PyPI

### For Addon Developers
1. **Study** the Smart Floater example
2. **Follow** the addon development guide
3. **Create** addons in `addons/` directory
4. **Test** with GGUF Loader
5. **Share** with community

## 📊 Package Statistics

### Size and Dependencies
- **Package Size**: ~50MB (includes all dependencies)
- **Core Dependencies**: 5 main packages
- **Optional Dependencies**: GPU acceleration packages
- **Documentation**: 10+ comprehensive guides

### Compatibility
- **Python**: 3.8+ (tested on 3.8, 3.9, 3.10, 3.11, 3.12)
- **Operating Systems**: Windows, macOS, Linux
- **Architectures**: x86_64, ARM64 (Apple Silicon)

## 🔍 Troubleshooting Package Issues

### Common Installation Issues
1. **Python Version**: Ensure Python 3.8+
2. **Dependencies**: Install build tools if needed
3. **Permissions**: Use `--user` flag if needed
4. **Virtual Environment**: Recommended for isolation

### Addon Loading Issues
1. **Check Logs**: Look for addon loading errors
2. **Verify Structure**: Ensure `__init__.py` exists
3. **Dependencies**: Check addon-specific requirements
4. **Permissions**: Verify file permissions

### Getting Help
- **Documentation**: Check `docs/` folder
- **GitHub Issues**: Report bugs and issues
- **Community**: Join discussions and forums
- **Support**: Contact support@ggufloader.com

## 🎉 Success Metrics

The package structure is designed to provide:
- **Easy Installation**: Single `pip install` command
- **Immediate Functionality**: Smart Floater works out of the box
- **Extensibility**: Clear addon development path
- **Maintainability**: Well-organized codebase
- **User-Friendly**: Comprehensive documentation

---

**This package structure ensures that GGUF Loader 2.0.0 provides a complete, professional AI text processing solution with the Smart Floating Assistant included by default! 🚀**