# Installation Guide

This guide will help you install GGUF Loader 2.0.0 on your system.

## 🚀 Quick Installation

### Using pip (Recommended)

```bash
pip install ggufloader
```

That's it! You can now run GGUF Loader with:

```bash
ggufloader
```

## 📋 System Requirements

### Minimum Requirements
- **Python**: 3.8 or higher
- **RAM**: 4GB (8GB+ recommended for larger models)
- **Storage**: 2GB free space for models
- **OS**: Windows 10/11, macOS 10.14+, or Linux

### Recommended Requirements
- **Python**: 3.10 or higher
- **RAM**: 16GB or more
- **GPU**: NVIDIA GPU with CUDA support (optional but recommended)
- **Storage**: 10GB+ free space for multiple models

## 🔧 Detailed Installation

### Step 1: Install Python

If you don't have Python installed:

#### Windows
1. Download Python from [python.org](https://www.python.org/downloads/)
2. Run the installer and check "Add Python to PATH"
3. Verify installation: `python --version`

#### macOS
```bash
# Using Homebrew (recommended)
brew install python

# Or download from python.org
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3 python3-pip
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv ggufloader-env

# Activate it
# Windows:
ggufloader-env\Scripts\activate
# macOS/Linux:
source ggufloader-env/bin/activate
```

### Step 3: Install GGUF Loader

```bash
pip install ggufloader
```

### Step 4: Verify Installation

```bash
ggufloader --version
```

## 🎮 First Run

### Launch GGUF Loader

```bash
ggufloader
```

This will open the GGUF Loader application with the Smart Floating Assistant addon already loaded.

### Load Your First Model

1. **Download a GGUF model** (e.g., from Hugging Face)
2. **Click "Select GGUF Model"** in the application
3. **Choose your model file**
4. **Wait for loading** (may take a few minutes)
5. **Start chatting!**

## 🔧 GPU Acceleration (Optional)

For better performance with larger models, you can enable GPU acceleration:

### NVIDIA GPU (CUDA)

```bash
# Uninstall CPU version
pip uninstall llama-cpp-python

# Install GPU version
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

### Apple Silicon (Metal)

```bash
# Uninstall CPU version
pip uninstall llama-cpp-python

# Install Metal version
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python
```

## 🛠️ Advanced Installation

### Development Installation

If you want to contribute or modify GGUF Loader:

```bash
# Clone the repository
git clone https://github.com/gguf-loader/gguf-loader.git
cd gguf-loader

# Install in development mode
pip install -e .

# Install development dependencies
pip install -e .[dev]
```

### Custom Installation Location

```bash
# Install to specific directory
pip install --target /path/to/directory ggufloader

# Add to Python path
export PYTHONPATH="/path/to/directory:$PYTHONPATH"
```

## 🐛 Troubleshooting Installation

### Common Issues

#### Issue: "pip not found"
```bash
# Windows
python -m pip install ggufloader

# macOS/Linux
python3 -m pip install ggufloader
```

#### Issue: "Permission denied"
```bash
# Use --user flag
pip install --user ggufloader

# Or use virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
pip install ggufloader
```

#### Issue: "Package not found"
```bash
# Update pip first
pip install --upgrade pip

# Then install
pip install ggufloader
```

#### Issue: "SSL Certificate error"
```bash
# Use trusted hosts
pip install --trusted-host pypi.org --trusted-host pypi.python.org ggufloader
```

### Platform-Specific Issues

#### Windows
- **Issue**: "Microsoft Visual C++ 14.0 is required"
  - **Solution**: Install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

#### macOS
- **Issue**: "Command line tools not found"
  - **Solution**: `xcode-select --install`

#### Linux
- **Issue**: Missing system dependencies
  ```bash
  # Ubuntu/Debian
  sudo apt install build-essential python3-dev
  
  # CentOS/RHEL
  sudo yum groupinstall "Development Tools"
  sudo yum install python3-devel
  ```

## 🔄 Updating GGUF Loader

### Update to Latest Version

```bash
pip install --upgrade ggufloader
```

### Check Current Version

```bash
ggufloader --version
```

### Downgrade if Needed

```bash
pip install ggufloader==1.0.0  # Replace with desired version
```

## 🗑️ Uninstallation

### Remove GGUF Loader

```bash
pip uninstall ggufloader
```

### Clean Up Dependencies (Optional)

```bash
# List installed packages
pip list

# Remove specific dependencies if not needed elsewhere
pip uninstall llama-cpp-python PySide6 pyautogui pyperclip
```

### Remove Configuration Files

```bash
# Windows
rmdir /s "%APPDATA%\ggufloader"

# macOS/Linux
rm -rf ~/.config/ggufloader
rm -rf ~/.local/share/ggufloader
```

## 📦 Alternative Installation Methods

### Using conda

```bash
# Create conda environment
conda create -n ggufloader python=3.10
conda activate ggufloader

# Install via pip (no conda package yet)
pip install ggufloader
```

### Using pipx (Isolated Installation)

```bash
# Install pipx if not already installed
pip install pipx

# Install ggufloader in isolated environment
pipx install ggufloader

# Run
ggufloader
```

### From Source

```bash
# Download source
wget https://github.com/gguf-loader/gguf-loader/archive/v2.0.0.tar.gz
tar -xzf v2.0.0.tar.gz
cd gguf-loader-2.0.0

# Install
pip install .
```

## 🎯 Next Steps

After installation:

1. **Read the [Quick Start Guide](quick-start.md)** to get up and running
2. **Check out the [User Guide](user-guide.md)** for detailed usage instructions
3. **Explore [Addon Development](addon-development.md)** to create custom addons
4. **Join our [community](https://github.com/gguf-loader/gguf-loader/discussions)** for support and discussions

## 💡 Need Help?

- 📖 Check the [Troubleshooting Guide](troubleshooting.md)
- 🐛 [Report installation issues](https://github.com/gguf-loader/gguf-loader/issues)
- 💬 [Ask for help in discussions](https://github.com/gguf-loader/gguf-loader/discussions)
- 📧 Contact us: support@ggufloader.com

---

**Welcome to GGUF Loader! 🎉**