#!/bin/bash
# Build script for creating GGUF Loader executable on Linux (WITH ADDON SUPPORT)
# Mirrors scripts/build_exe.bat. Run from anywhere; changes to project root.

set -e
cd "$(dirname "$0")/.."

echo "========================================"
echo "GGUF Loader - Linux Executable Builder"
echo "WITH ADDON SUPPORT (Floating Chat)"
echo "========================================"
echo

# Check if virtual environment exists
if [ ! -f ".venv/bin/activate" ]; then
    echo "[ERROR] Virtual environment not found!"
    echo "Please run: python3 -m venv .venv"
    echo "Then activate it and install requirements"
    exit 1
fi

# Activate virtual environment
echo "[1/4] Activating virtual environment..."
source .venv/bin/activate

# Install PyInstaller if not already installed
echo
echo "[2/4] Installing PyInstaller..."
pip install pyinstaller

# Clean previous builds
echo
echo "[3/4] Cleaning previous builds..."
rm -rf build dist

# Build executable
echo
echo "[4/4] Building executable..."
pyinstaller build_exe.spec

# Check if build was successful
if [ -f "dist/GGUFLoader_WithAddons" ]; then
    echo
    echo "========================================"
    echo "BUILD SUCCESSFUL!"
    echo "========================================"
    echo
    echo "Your SINGLE EXECUTABLE file is located at:"
    echo "dist/GGUFLoader_WithAddons"
    echo
    echo "Rename it for release, e.g.:"
    TAG_VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "unknown")
    TAG_VERSION=${TAG_VERSION#v}
    echo "mv dist/GGUFLoader_WithAddons dist/GGUFLoader_Linux_x86_64_v${TAG_VERSION}"
    echo
    echo "Note: onefile binaries are NOT cross-platform - this build"
    echo "must run on Linux (the GitHub Actions workflow does this"
    echo "automatically on tag pushes)."
    echo
else
    echo
    echo "========================================"
    echo "BUILD FAILED!"
    echo "========================================"
    echo "Please check the error messages above."
    echo
    exit 1
fi
