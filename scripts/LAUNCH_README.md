# GGUF Loader - Launch Scripts

This document covers the launch scripts for Windows, macOS, and Linux that live in the **project root** (`launch.bat` / `launch.sh`).

## Files

- `launch.bat` (project root) - Launches the full GGUF Loader application with addon support (Windows)
- `launch.sh` (project root) - Launches the full GGUF Loader application with addon support (macOS and Linux)

## Usage

### Windows
Simply double-click on `launch.bat` to run the application:

1. If a Python virtual environment doesn't exist, it will be created automatically
2. Required dependencies will be installed
3. The application will start

### macOS and Linux
Run the launch script from the terminal:

```bash
./launch.sh
```

1. If a Python virtual environment doesn't exist, it will be created automatically
2. Required dependencies will be installed
3. The application will start

## Requirements

- Python 3.7 or higher must be installed and accessible from the command line

## Troubleshooting

If you encounter issues:

1. Ensure Python is installed and added to your PATH
2. Try deleting the `.venv` folder and running the script again
3. Check that your antivirus isn't blocking the virtual environment creation