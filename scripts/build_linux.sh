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

# Clean previous builds. Keep other dist artifacts - only remove this build's
# stale output (mirrors scripts/build_exe.bat).
echo
echo "[3/4] Cleaning previous builds..."
rm -rf build
rm -f dist/GGUFLoader_WithAddons

# Build executable
echo
echo "[4/4] Building executable..."
pyinstaller build_exe.spec

# Resolve the app version (single source of truth: ggufloader/_version.py).
# Linux builds are always CPU-only here (requirements.txt installs the plain
# CPU wheel), hence the _CPU suffix.
VERSION=$(python -c "from ggufloader._version import __version__; print(__version__)" 2>/dev/null || echo "unknown")
FINAL_NAME="GGUFLoader_v${VERSION}_linux_x86_64_CPU"

# Check if build was successful
if [ -f "dist/GGUFLoader_WithAddons" ]; then
    mv "dist/GGUFLoader_WithAddons" "dist/${FINAL_NAME}"
    echo
    echo "========================================"
    echo "BUILD SUCCESSFUL!"
    echo "========================================"
    echo
    echo "Your SINGLE EXECUTABLE file is located at:"
    echo "dist/${FINAL_NAME}"
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
