# GGUF Loader - Quick Reference

## 📖 Documentation Quick Links

### I want to...

**Install GGUF Loader**
→ [Installation Guide](docs/installation.md)

**Learn how to use it**
→ [User Guide](docs/user-guide.md)

**Get answers to questions**
→ [FAQ](docs/faq.md)

**Create an addon**
→ [Addon Development](docs/addon-development.md)

**Set up feedback system**
→ [Feedback System](docs/feedback-system.md)

**Contribute to the project**
→ [Contributing Guide](CONTRIBUTING.md)

**Find all documentation**
→ [Documentation Index](DOCUMENTATION.md)

## 🚀 Quick Start

### Install
```bash
pip install ggufloader
```

### Run
```bash
ggufloader
```

### Or use Windows executable
[Download here](https://github.com/GGUFloader/gguf-loader/releases)

## 📥 Download Models

**Recommended starter models:**
- [Mistral-7B Q4_0 (4.23 GB)](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF/resolve/main/mistral-7b-instruct-v0.1.Q4_0.gguf)
- [LLaMA 3 8B Q4_0 (4.68 GB)](https://huggingface.co/TheBloke/Llama-3-8B-Instruct-GGUF/resolve/main/llama-3-8b-instruct.Q4_0.gguf)

## 🎯 Common Tasks

### Load a Model
1. Click "Load Model"
2. Select your `.gguf` file
3. Wait for loading
4. Start chatting!

### Use Smart Floater
1. Select text anywhere
2. Click the ✨ button
3. Choose action (Summarize/Comment)
4. Get AI response

### Install an Addon
1. Place addon folder in `addons/`
2. Restart GGUF Loader
3. Check addon sidebar

## 🐛 Troubleshooting

**Model won't load?**
→ Check [FAQ - Model Issues](docs/faq.md#models)

**App won't start?**
→ Check [FAQ - Installation](docs/faq.md#installation)

**Slow performance?**
→ Check [FAQ - Performance](docs/faq.md#performance)

## 📞 Get Help

- 📖 [FAQ](docs/faq.md)
- 💬 [Discussions](https://github.com/GGUFloader/gguf-loader/discussions)
- 🐛 [Issues](https://github.com/GGUFloader/gguf-loader/issues)
- 📧 hossainnazary475@gmail.com

## 📁 File Structure

```
Root Files:
├── README.md              # Project overview
├── DOCUMENTATION.md       # Documentation index
├── QUICK_REFERENCE.md     # This file
└── CONTRIBUTING.md        # How to contribute

Documentation:
└── docs/
    ├── installation.md    # Install guide
    ├── user-guide.md      # User manual
    ├── addon-development.md # Addon guide
    ├── feedback-system.md # Feedback setup
    └── faq.md            # FAQ
```

## ⚡ Keyboard Shortcuts

- **Enter** - Send message
- **Shift+Enter** - New line
- **Ctrl+L** - Clear chat
- **Ctrl+K** - Load model

## 🔧 System Requirements

**Minimum:**
- 4GB RAM
- 2GB storage
- Windows 10/Linux/macOS

**Recommended:**
- 8GB+ RAM
- 10GB+ storage
- GPU (optional)

## 📊 Model Size Guide

| RAM | Recommended Model |
|-----|-------------------|
| 4GB | Q4_0 (4-5GB) |
| 8GB | Q6_K (6-7GB) |
| 16GB+ | Q8_0 or larger |

---

**Version:** 2.0.1
**Last Updated:** January 2026
