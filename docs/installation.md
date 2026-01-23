# Installation Guide

This guide covers all installation methods for GGUF Loader.

## Method 1: Windows Executable (Easiest)

1. Download the latest release: [GGUFLoader.2.0.1.exe](https://github.com/GGUFloader/gguf-loader/releases/download/v2.0.1/GGUFLoader.2.0.1.exe)
2. Run the executable
3. No Python installation required!

## Method 2: Install via pip

```bash
pip install ggufloader
ggufloader
```

## Method 3: Run from Source

### Prerequisites
- Python 3.7 or higher
- Git (optional)

### Windows

1. Clone or download the repository
2. Double-click `launch.bat`
3. The script will automatically:
   - Create a virtual environment
   - Install dependencies
   - Launch the application

### Linux/macOS

1. Clone or download the repository
2. Make the script executable:
   ```bash
   chmod +x launch.sh
   ```
3. Run the script:
   ```bash
   ./launch.sh
   ```

## Basic vs Full Version

### Full Version (Recommended)
- Includes addon system
- Smart Floating Assistant
- All features enabled

**Launch:**
- Windows: `launch.bat`
- Linux/macOS: `./launch.sh`

### Basic Version
- Core chat functionality only
- No addons
- Lighter weight

**Launch:**
- Windows: `launch_basic.bat`
- Linux/macOS: `./launch_basic.sh`

## Troubleshooting

### Python Not Found
Ensure Python 3.7+ is installed and added to your PATH.

### Permission Denied (Linux/macOS)
```bash
chmod +x launch.sh
```

### Antivirus Blocking
Some antivirus software may flag the executable. Add an exception if needed.

### Dependencies Fail to Install
Try manually installing:
```bash
pip install -r requirements.txt
```

## Next Steps

After installation, see the [User Guide](user-guide.md) to get started.
