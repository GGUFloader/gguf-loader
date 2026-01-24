# GGUF Loader

![GitHub License](https://img.shields.io/github/license/ggufloader/gguf-loader)
![GitHub Last Commit](https://img.shields.io/github/last-commit/ggufloader/gguf-loader)
[![PyPI - Version](https://img.shields.io/pypi/v/ggufloader)](https://pypi.org/project/ggufloader/)

A beginner-friendly, privacy-first desktop application for running large language models locally on Windows, Linux, and macOS. Load and chat with GGUF format models like Mistral, LLaMA, DeepSeek, and others with zero setup required.

## 🚀 Quick Start

### Option 1: Windows Executable (Easiest - Recommended)

**Step 1: Download the App**
[![Download GGUF Loader v2.1.0](https://img.shields.io/badge/Download%20GGUF%20Loader-v2.1.0-blue?style=for-the-badge&logo=github)](https://github.com/GGUFloader/gguf-loader/releases/download/v2.1.0/GGUFLoader_v2.1.0.exe)

**Direct Download:** [GGUFLoader_v2.1.0.exe](https://github.com/GGUFloader/gguf-loader/releases/download/v2.1.0/GGUFLoader_v2.1.0.exe) (~150-300 MB)

**Step 2: Run the App**
1. Click the downloaded `GGUFLoader_v2.1.0.exe` file
2. Windows may show a security warning - click "More info" then "Run anyway" (this is normal for new apps)
3. The app will start automatically - no installation needed!

**Step 3: Download a Model**
- Visit [Local AI Zone](https://local-ai-zone.github.io/) for curated model recommendations
- Or browse [Hugging Face](https://huggingface.co/models?library=gguf) for thousands of GGUF models
- Save it anywhere on your computer (e.g., Downloads folder)

**Step 4: Load the Model**
1. In GGUF Loader, click "Load Model" button
2. Browse to where you saved your GGUF model file
3. Select the model and click "Open"
4. Wait for the model to load (progress bar will show)

**Step 5: Start Chatting!**
1. Look for the floating chat button on your screen
2. Click it to open the chat window
3. Type your message and press Ctrl+Enter or click "Send"
4. Enjoy your private, local AI assistant!

---

### Option 2: Install via pip

```bash
pip install ggufloader
ggufloader
```

---

### Option 3: Run from Source (No Installation Required)

> 💡 **Easy method - No coding knowledge needed!**

**Step 1: Download the ZIP file**
- Click here: [Download ZIP](https://github.com/GGUFloader/gguf-loader/archive/refs/heads/main.zip)
- Save it anywhere on your computer

**Step 2: Extract the ZIP file**
- Right-click on the downloaded ZIP file
- Select "Extract All..." (Windows) or "Extract Here" (Linux/macOS)
- Choose where to extract it

**Step 3: Run the launcher**

**For Windows:**
- Open the extracted folder
- Double-click on `launch.bat`
- **First time only**: Wait 1-2 minutes while it downloads dependencies
- The app will start automatically!
- **Next time**: Just double-click `launch.bat` again - it starts instantly!

**For Linux/macOS:**
- Open the extracted folder
- Double-click on `launch.sh` (or right-click → Open)
- **First time only**: Wait 1-2 minutes while it downloads dependencies
- The app will start automatically!
- **Next time**: Just double-click `launch.sh` again - it starts instantly!

**That's it!** No Python installation needed, no command line, no complicated setup.

---

## ✨ Features

- 🤖 **Universal Model Support** - Load ANY GGUF model from anywhere, not limited to pre-installed models
- 🔄 **Zero-Setup Model Loading** - Use any downloaded GGUF model instantly without configuration or conversion
- 🎨 **Modern UI** - Clean, intuitive interface built with PySide6
- 🔌 **Powerful Addon System** - Enhance functionality by creating custom addons without modifying core code
- 🌐 **Floating Chat Button** - Always-accessible chat interface that stays on top of all windows
- 🔒 **Privacy First** - All processing happens locally on your machine, no data leaves your computer
- 💻 **Cross-Platform** - Works seamlessly on Windows, Linux, and macOS
- ⚡ **Lightweight & Fast** - Efficient memory usage and quick response times
- 🎯 **Beginner Friendly** - No technical knowledge required, just download and run

## 📥 Download Models

### Recommended Models

**GPT-OSS 20B** (7.34 GB)
- [⬇️ Download Q4_K](https://huggingface.co/lmstudio-community/gpt-oss-20b-GGUF/resolve/main/gpt-oss-20b-MXFP4.gguf)

**Mistral-7B Instruct** (4.23 GB)
- [⬇️ Download Q4_0](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF/resolve/main/mistral-7b-instruct-v0.1.Q4_0.gguf)

**LLaMA 3 8B Instruct** (4.68 GB)
- [⬇️ Download Q4_0](https://huggingface.co/TheBloke/Llama-3-8B-Instruct-GGUF/resolve/main/llama-3-8b-instruct.Q4_0.gguf)

[More models available →](https://local-ai-zone.github.io)

## 📚 Documentation

- **[Quick Reference](QUICK_REFERENCE.md)** - Fast answers to common tasks
- **[Installation Guide](docs/installation.md)** - Detailed setup instructions
- **[User Guide](docs/user-guide.md)** - How to use GGUF Loader
- **[Addon Development](docs/addon-development.md)** - Create your own addons
- **[FAQ](docs/faq.md)** - Frequently asked questions
- **[All Documentation](DOCUMENTATION.md)** - Complete documentation index

## 🎬 Demo Video

[![Watch Demo](https://img.youtube.com/vi/5lQui7EeUe0/maxresdefault.jpg)](https://www.youtube.com/watch?v=5lQui7EeUe0)

## 🛠️ System Requirements

- **OS:** Windows 10/11, Linux, or macOS
- **RAM:** 4GB minimum (8GB recommended)
- **Storage:** 2GB free space
- **GPU:** Optional (CUDA/OpenCL support)

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## 🔒 Security

Report security vulnerabilities to: hossainnazary475@gmail.com

See [SECURITY.md](SECURITY.md) for our security policy.

## 📞 Support

- 🐛 [Report Issues](https://github.com/GGUFloader/gguf-loader/issues)
- 💬 [Discussions](https://github.com/GGUFloader/gguf-loader/discussions)
- 📧 Email: hossainnazary475@gmail.com

---

**Built with ❤️ by the GGUF Loader community**
