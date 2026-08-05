# GGUF Loader

![GitHub License](https://img.shields.io/github/license/ggufloader/gguf-loader)
![GitHub Last Commit](https://img.shields.io/github/last-commit/ggufloader/gguf-loader)
[![PyPI - Version](https://img.shields.io/pypi/v/ggufloader)](https://pypi.org/project/ggufloader/)

> 🎉 **NEW: Agentic Mode Now Available!** Transform your local AI into an autonomous coding assistant that can read, create, edit, and organize files in your workspace. Perfect for automating development tasks, generating boilerplate code, and managing complex workflows - all running privately on your machine. [Learn more about Agentic Mode →](#-agentic-mode)

A beginner-friendly, privacy-first desktop application for running large language models locally on Windows, Linux, and macOS. Load and chat with GGUF format models like Mistral, LLaMA, DeepSeek, and others with zero setup required.

## 🚀 Quick Start

### Option 1: Windows Executable (Easiest - Recommended)

**Step 1: Download the App**
[![Download GGUF Loader v2.1.1 Agentic Mode](https://img.shields.io/badge/Download%20GGUF%20Loader-v2.1.1%20Agentic%20Mode-blue?style=for-the-badge&logo=github)](https://github.com/GGUFloader/gguf-loader/releases/download/v2.1.1/GGUFLoader_v2.1.1.agentic_mode.exe)

**Direct Download:** [GGUFLoader_v2.1.1.agentic_mode.exe](https://github.com/GGUFloader/gguf-loader/releases/download/v2.1.1/GGUFLoader_v2.1.1.agentic_mode.exe) (~150-300 MB)

**Step 2: Run the App**
1. Click the downloaded `GGUFLoader_v2.1.1.agentic_mode.exe` file
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
- 🤖 **Agentic Mode** - Advanced reasoning and task automation with multi-step problem solving
- 🔒 **Privacy First** - All processing happens locally on your machine, no data leaves your computer
- 💻 **Cross-Platform** - Works seamlessly on Windows, Linux, and macOS
- ⚡ **Lightweight & Fast** - Efficient memory usage and quick response times
- 🎯 **Beginner Friendly** - No technical knowledge required, just download and run

## 📥 Download Models

### Recommended Models

**Mistral-7B Instruct** (4.23 GB) - **Recommended for Agentic Mode**
- [⬇️ Download Q4_0](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF/resolve/main/mistral-7b-instruct-v0.1.Q4_0.gguf)
- Excellent reasoning and task automation capabilities
- Perfect for agentic workflows and multi-step problem solving
- Fast inference with strong instruction following

**GPT-OSS 20B** (7.34 GB)
- [⬇️ Download Q4_K](https://huggingface.co/lmstudio-community/gpt-oss-20b-GGUF/resolve/main/gpt-oss-20b-MXFP4.gguf)

**LLaMA 3 8B Instruct** (4.68 GB)
- [⬇️ Download Q4_0](https://huggingface.co/TheBloke/Llama-3-8B-Instruct-GGUF/resolve/main/llama-3-8b-instruct.Q4_0.gguf)

[More models available →](https://local-ai-zone.github.io)

## 📚 Documentation

- **[Quick Reference](QUICK_REFERENCE.md)** - Fast answers to common tasks
- **[Installation Guide](docs/installation.md)** - Detailed setup instructions
- **[User Guide](docs/user-guide.md)** - How to use GGUF Loader
- **[Addon Development](docs/addon-development.md)** - Create your own addons
- **[FAQ](docs/faq.md)** - Frequently asked questions
- **[All Documentation](docs/DOCUMENTATION.md)** - Complete documentation index
- **[Architecture](ARCHITECTURE.md)** - Layered design, threading model, and extension guide

## 🤖 Agentic Mode

GGUF Loader now supports agentic mode, enabling the AI assistant to autonomously manage your workspace. The assistant can read, create, edit, and organize files within your project folder, automating development tasks and workflows.

### What Agentic Mode Can Do

- **Read Files** - Analyze code, documentation, and project structure
- **Create Files** - Generate new source files, configs, and documentation
- **Edit Files** - Modify existing code and update configurations
- **Organize Files** - Create folders, move files, and restructure projects
- **Automate Tasks** - Execute multi-step workflows without manual intervention

### Getting Started with Agentic Mode

1. **Load Mistral-7B** (recommended for best results)
   - Download from the models section above
   - Load it in GGUF Loader

2. **Enable Agentic Mode**
   - Open the chat window
   - Select "Agentic Mode" from the settings
   - Grant workspace access permissions

3. **Example Tasks**
   - "Create a new feature module with proper structure"
   - "Refactor this codebase and organize files"
   - "Generate boilerplate code for a new component"
   - "Update all configuration files with new settings"
   - "Create documentation for this project"

### Model Recommendations for Agentic Mode

- **Mistral-7B Instruct** ⭐ Best choice - excellent reasoning, fast inference, perfect for code generation
- **LLaMA 3 8B** - Strong reasoning and code understanding
- **GPT-OSS 20B** - More powerful for complex refactoring tasks

## 🎬 Screenshot

![GGUF Loader Interface](screen.png)

## 🛠️ System Requirements

- **OS:** Windows 10/11, Linux, or macOS
- **RAM:** 4GB minimum (8GB recommended)
- **Storage:** 2GB free space
- **GPU:** Optional (CUDA/OpenCL support)

## 🚀 GPU Acceleration (Optional)

GGUF Loader supports GPU acceleration for significantly faster inference speeds. If you have an NVIDIA GPU, follow these steps:

### Prerequisites
- NVIDIA GPU (GTX 1060 or newer recommended)
- CUDA Toolkit installed (CUDA 12.x recommended)
- Latest NVIDIA drivers

### Installation Steps

**Step 1: Run the GPU installation script**

**Option A: Pre-built wheel (Recommended - Fastest)**
```bash
# Windows
scripts/install_gpu_llama.bat

# Linux/macOS
chmod +x scripts/install_gpu_llama.sh
./scripts/install_gpu_llama.sh
```

**Option B: Build from source (requires a C++ compiler, CMake, and CUDA Toolkit; Metal on macOS)**
```bash
# Windows
scripts/install_gpu_llama_source.bat

# Linux/macOS
chmod +x scripts/install_gpu_llama_source.sh
./scripts/install_gpu_llama_source.sh
```

**Step 2: Verify GPU support**
```bash
python scripts/verify_gpu_support.py
```

**Step 3: Use GPU acceleration**
1. Launch GGUF Loader
2. In the "Processing Mode" dropdown, select **"GPU Accelerated"**
3. Load your model - you'll see "(GPU)" in the status
4. Start chatting with GPU-accelerated inference!

### Performance Tips
- **RTX 4060 (8GB):** Can offload 25-40 layers depending on model size
- **RTX 3060 (12GB):** Can offload 40-50 layers
- **RTX 4090 (24GB):** Can offload entire models (60+ layers)

### Monitoring GPU Usage
Run this in a separate terminal while using GGUF Loader:
```bash
# Windows
scripts/monitor_gpu.bat

# Linux/macOS
watch -n 1 nvidia-smi
```

Watch the "GPU-Util" column increase when generating responses - this confirms GPU acceleration is working!

### Troubleshooting
- **"pip not recognized"**: The script will automatically activate your virtual environment
- **Slow speeds**: Try increasing GPU layers in `models/model_loader.py` (default: 35)
- **Out of memory**: Reduce GPU layers or use a smaller model
- **No speedup**: Verify CUDA is installed with `nvidia-smi`

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
