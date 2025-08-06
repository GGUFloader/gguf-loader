
📄 **Machine-readable metadata available**  
- [metadata.json](./metadata.json)  
- [meta.yaml](./meta.yaml)

# GGUF Loader
![GitHub License](https://img.shields.io/github/license/ggufloader/gguf-loader)
![GitHub Last Commit](https://img.shields.io/github/last-commit/ggufloader/gguf-loader)
![Repo Size](https://img.shields.io/github/repo-size/ggufloader/gguf-loader)
![Open Issues](https://img.shields.io/github/issues/ggufloader/gguf-loader)

[![PyPI - Version](https://img.shields.io/pypi/v/ggufloader)](https://pypi.org/project/ggufloader/)
[![PyPI - Wheel](https://img.shields.io/pypi/wheel/ggufloader)](https://pypi.org/project/ggufloader/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ggufloader)](https://pypi.org/project/ggufloader/)
[![PyPI Downloads](https://static.pepy.tech/badge/ggufloader)](https://pepy.tech/projects/ggufloader)


---


A beginner-friendly, privacy-first desktop application for running large language models locally on Windows. Run models like Mistral, LLaMA, DeepSeek, and others in GGUF format with zero setup required.

## Download EXE file for Windows
[![Download GGUF Loader v2.0.1](https://img.shields.io/badge/Download%20GGUF%20Loader-v2.0.1-blue?style=for-the-badge&logo=github)](https://github.com/GGUFloader/gguf-loader/releases/download/v2.0.1/GGUFLoader.2.0.1.exe
)



## 🚀 Install in One Line

```bash
pip install ggufloader
```

```bash
ggufloader
```
## 🧩 🎬 Demo Video: Addon System + Floating Tool in Local LLM (v2.0.1 Update)

[![Watch the video](https://img.youtube.com/vi/5lQui7EeUe0/maxresdefault.jpg)](https://www.youtube.com/watch?v=5lQui7EeUe0)



> Discover how to supercharge your local AI workflows using the new floating addon system! No coding needed. Works offline.


Works on Windows, Linux, and macOS.
## 🔽 Download GGUF Models

> ⚡ Click a link below to download the model file directly (no Hugging Face page in between).
### 🧠 GPT-OSS Models (Open Source GPTs)

> High-quality, Apache 2.0 licensed, reasoning-focused models for local/enterprise use.

#### 🧠 GPT-OSS 120B (Dense)

- [⬇️ Download Q4_K (46.2 GB)](https://huggingface.co/lmstudio-community/gpt-oss-120b-GGUF/resolve/main/gpt-oss-120b-MXFP4-00001-of-00002.gguf)


#### 🧠 GPT-OSS 20B (Dense)

- [⬇️ Download Q4_K (7.34 GB)](https://huggingface.co/lmstudio-community/gpt-oss-20b-GGUF/resolve/main/gpt-oss-20b-MXFP4.gguf)



---
### 🧠 Mistral-7B Instruct

- [⬇️ Download Q4_0 (4.23 GB)](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF/resolve/main/mistral-7b-instruct-v0.1.Q4_0.gguf)
- [⬇️ Download Q6_K (6.23 GB)](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF/resolve/main/mistral-7b-instruct-v0.1.Q6_K.gguf)

### 🧠 Qwen 1.5-7B Chat

- [⬇️ Download Q4_K (4.88 GB)](https://huggingface.co/TheBloke/Qwen1.5-7B-Chat-GGUF/resolve/main/qwen1_5-7b-chat-q4_k.gguf)
- [⬇️ Download Q6_K (6.83 GB)](https://huggingface.co/TheBloke/Qwen1.5-7B-Chat-GGUF/resolve/main/qwen1_5-7b-chat-q6_k.gguf)

### 🧠 DeepSeek 7B Chat

- [⬇️ Download Q4_0 (4.87 GB)](https://huggingface.co/TheBloke/DeepSeek-7B-Chat-GGUF/resolve/main/deepseek-7b-chat.Q4_0.gguf)
- [⬇️ Download Q8_0 (9.33 GB)](https://huggingface.co/TheBloke/DeepSeek-7B-Chat-GGUF/resolve/main/deepseek-7b-chat.Q8_0.gguf)

### 🧠 LLaMA 3 8B Instruct

- [⬇️ Download Q4_0 (4.68 GB)](https://huggingface.co/TheBloke/Llama-3-8B-Instruct-GGUF/resolve/main/llama-3-8b-instruct.Q4_0.gguf)
- [⬇️ Download Q6_K (6.91 GB)](https://huggingface.co/TheBloke/Llama-3-8B-Instruct-GGUF/resolve/main/llama-3-8b-instruct.Q6_K.gguf)


---

### 🗂️ More Model Collections

- [🧠 TheBloke’s GGUF Model Collection](https://local-ai-zone.github.io)
- [🌍 GGUF Community Collection](https://local-ai-zone.github.io)

## Development Roadmap

| **Phase** | **Timeline** | **Status** | **Key Milestones & Features** |
|----------|--------------|------------|--------------------------------|
| **Phase 1: Core Foundation** | ✅ Q3 2025 | 🚀 In Progress | - Zero-setup installer<br>- Offline model loading (GGUF)<br>- Intuitive GUI (PySide6)<br>- Built-in tokenizer viewer<br>- Basic file summarizer (TXT/PDF) |
| **Phase 2: Addon Ecosystem** | 🔄 Q3–Q4 2025 | 🧪 In Development | - Addon manager + sidebar UI (✅ started)<br>- Addon popup architecture<br>- Example addon templates<br>- Addon activation/deactivation<br>- Addon SDK for easy integration |
| **Phase 3: Power User Features** | Q4 2025 | 📋 Planned | - GPU acceleration (Auto/Manual)<br>- Model browser + drag-and-run<br>- Prompt builder with reusable templates<br>- Dark/light theme toggle |
| **Phase 4: AI Automation Toolkit** | Q4 2025 – Q1 2026 | 🔬 Research | - RAG pipeline (Retrieval-Augmented Generation)<br>- Multi-document summarization<br>- Contract/book intelligence<br>- Agent workflows (write → summarize → reply) |
| **Phase 5: Cross-Platform & Sync** | 2026 | 🎯 Vision | - macOS and Linux support<br>- Auto-updating model index<br>- Cross-device config sync<br>- Voice command system (whisper.cpp integration) |
| **Phase 6: Public Ecosystem** | 2026+ | 🌐 Long-Term | - Addon marketplace <br>- Addon rating and discovery<br>- Developer CLI & SDK<br>- Community themes, extensions, and templates |


# GGUF Loader Documentation

Welcome to the GGUF Loader documentation! This guide will help you get started with GGUF Loader 2.0.0 and its powerful addon system.

## 📚 Documentation Index

### Getting Started
- [Installation Guide](installation.md) - How to install and set up GGUF Loader
- [Quick Start Guide](quick-start.md) - Get up and running in minutes
- [User Guide](user-guide.md) - Complete user manual

### Addon Development
- [Addon Development Guide](addon-development.md) - Create your own addons
- [Addon API Reference](addon-api.md) - Complete API documentation
- [Smart Floater Example](smart-floater-example.md) - Learn from the built-in addon

### Advanced Topics
- [Configuration](configuration.md) - Customize GGUF Loader settings
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [Performance Optimization](performance.md) - Get the best performance

### Developer Resources
- [Contributing Guide](contributing.md) - How to contribute to the project
- [Architecture Overview](architecture.md) - Technical architecture details
- [API Reference](api-reference.md) - Complete API documentation

## 🚀 What's New in Version 2.0.0

### Smart Floating Assistant
The flagship feature of version 2.0.0 is the **Smart Floating Assistant** addon:

- **Global Text Selection**: Works across all applications
- **AI-Powered Processing**: Summarize and comment on any text
- **Floating UI**: Non-intrusive, always-accessible interface
- **Privacy-First**: All processing happens locally

### Addon System
Version 2.0.0 introduces a powerful addon system:

- **Extensible Architecture**: Easy to create and install addons
- **Plugin API**: Rich API for addon development
- **Hot Loading**: Load and unload addons without restarting
- **Community Ecosystem**: Share addons with the community

## 🛠️ Quick Links

- **Installation**: `pip install ggufloader`
- **Launch**: `ggufloader` (includes Smart Floating Assistant)
- **GitHub**: [https://github.com/gguf-loader/gguf-loader](https://github.com/gguf-loader/gguf-loader)
- **Issues**: [Report bugs and request features](https://github.com/gguf-loader/gguf-loader/issues)

## 💡 Need Help?

- 📖 Check the [User Guide](user-guide.md) for detailed instructions
- 🐛 Found a bug? [Report it here](https://github.com/gguf-loader/gguf-loader/issues)
- 💬 Have questions? [Join our discussions](https://github.com/gguf-loader/gguf-loader/discussions)
- 📧 Contact us: support@ggufloader.com

---

**Happy coding with GGUF Loader! 🎉**
