# GGUF Loader - Launch Scripts

This directory contains launch scripts for Windows, macOS, and Linux to easily launch the GGUF Loader application.

## Files

- `launch.bat` - Launches the full GGUF Loader application with addon support (Windows)
- `launch_basic.bat` - Launches the basic GGUF Loader application without addons (Windows)
- `launch.sh` - Launches the full GGUF Loader application with addon support (macOS and Linux)
- `launch_basic.sh` - Launches the basic GGUF Loader application without addons (macOS and Linux)

## Usage

### Windows
Simply double-click on either batch file to run the application:

1. If a Python virtual environment doesn't exist, it will be created automatically
2. Required dependencies will be installed
3. The application will start

### macOS and Linux
Run the launch script from the terminal:

```bash
# For full version with addon support
./launch.sh

# For basic version without addons
./launch_basic.sh
```

1. If a Python virtual environment doesn't exist, it will be created automatically
2. Required dependencies will be installed
3. The application will start

## Requirements

- Python 3.7 or higher must be installed and accessible from the command line

## Troubleshooting

If you encounter issues:

1. Ensure Python is installed and added to your PATH
2. Try deleting the `venv` folder and running the script again
3. Check that your antivirus isn't blocking the virtual environment creation