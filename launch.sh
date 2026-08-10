#!/bin/bash

# GGUF Loader Launcher Script
# Creates a virtual environment if it doesn't exist, verifies that every
# dependency from requirements.txt is installed, installs anything that's
# missing, and then launches the application.
#
# Includes preflight checks that turn the most common setup failures into
# clear, actionable messages:
#   - Python missing or too old
#   - python3-venv missing (broken venv on Debian/Ubuntu)
#   - No C toolchain on Linux (llama-cpp-python is pulled from prebuilt
#     CPU wheels instead of being compiled from source)
#   - No network access to PyPI

# Change to the project root so relative paths work from anywhere
cd "$(dirname "$0")"

# Set the name of the virtual environment
VENV_NAME=".venv"
MIN_PY_MAJOR=3
MIN_PY_MINOR=10

# Function to print error messages and exit
error_exit() {
    echo "Error: $1" >&2
    exit 1
}

warn() {
    echo "Warning: $1" >&2
}

OS="$(uname -s)"

# ---------------------------------------------------------------------------
# 1. Python: must exist and be 3.10+
# ---------------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    error_exit "Python 3 is not installed. Install Python 3.10 or newer from https://www.python.org/downloads/ (on Debian/Ubuntu: sudo apt install python3), then run this script again."
fi

PY_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)"
if [ -z "$PY_VERSION" ]; then
    error_exit "Could not determine the Python version. Please check your Python installation."
fi
PY_MAJOR="${PY_VERSION%%.*}"
PY_MINOR="${PY_VERSION#*.}"
PY_MINOR="${PY_MINOR%%.*}"
if [ "$PY_MAJOR" -lt "$MIN_PY_MAJOR" ] || { [ "$PY_MAJOR" -eq "$MIN_PY_MAJOR" ] && [ "$PY_MINOR" -lt "$MIN_PY_MINOR" ]; }; then
    error_exit "Python $PY_VERSION is too old - GGUF Loader requires Python $MIN_PY_MAJOR.$MIN_PY_MINOR or newer."
fi
echo "Using Python $PY_VERSION"

# ---------------------------------------------------------------------------
# 2. Virtual environment: create it if missing, with a virtualenv fallback
#    for distros (e.g. Debian/Ubuntu) where `python3 -m venv` only works if
#    the separate python3-venv package is installed.
# ---------------------------------------------------------------------------
ensure_venv() {
    if [ -f "$VENV_NAME/bin/activate" ]; then
        return 0
    fi

    echo "Creating virtual environment..."
    if python3 -m venv "$VENV_NAME" 2>/dev/null && [ -f "$VENV_NAME/bin/activate" ]; then
        return 0
    fi

    warn "python3 -m venv did not create a usable environment (on Debian/Ubuntu this usually means 'python3-venv' is missing). Trying virtualenv..."
    if python3 -m virtualenv -q "$VENV_NAME" 2>/dev/null && [ -f "$VENV_NAME/bin/activate" ]; then
        return 0
    fi

    warn "virtualenv is not available either; trying to install it with pip..."
    if python3 -m pip install --user --quiet virtualenv 2>/dev/null \
       && python3 -m virtualenv -q "$VENV_NAME" 2>/dev/null \
       && [ -f "$VENV_NAME/bin/activate" ]; then
        return 0
    fi

    error_exit "Could not create a virtual environment. Fix one of these, then run this script again:
  - Debian/Ubuntu:  sudo apt install python3-venv
  - Any distro:     python3 -m pip install --user virtualenv
  - Or:             sudo apt install virtualenv"
}

ensure_venv

echo "Activating virtual environment..."
source "$VENV_NAME/bin/activate" || error_exit "Failed to activate the virtual environment at $VENV_NAME/bin/activate."

# pip must exist inside the venv
if ! python -m pip --version >/dev/null 2>&1; then
    error_exit "pip is missing inside the virtual environment. Recreate it with:
  rm -rf $VENV_NAME
  python3 -m venv $VENV_NAME        # Debian/Ubuntu: sudo apt install python3-venv first
  or: python3 -m virtualenv $VENV_NAME
then run this script again."
fi

# ---------------------------------------------------------------------------
# 3. Linux toolchain: llama-cpp-python has no prebuilt PyPI wheel on Linux,
#    so pip compiles it from source and needs gcc/g++/cmake/make. If the
#    toolchain is missing, fall back to abetlen's prebuilt CPU wheel index.
# ---------------------------------------------------------------------------
if [ "$OS" = "Linux" ]; then
    MISSING_TOOLS=""
    for tool in gcc g++ cmake make; do
        command -v "$tool" >/dev/null 2>&1 || MISSING_TOOLS="$MISSING_TOOLS $tool"
    done
    if [ -n "$MISSING_TOOLS" ]; then
        warn "Missing build tools:$MISSING_TOOLS"
        warn "llama-cpp-python normally needs these to compile from source on Linux, but"
        warn "this script installs abetlen's prebuilt CPU wheels instead, so they are optional:"
        warn "  Debian/Ubuntu:  sudo apt install build-essential cmake"
        warn "  Fedora:         sudo dnf install gcc-c++ cmake make"
        warn "  Arch:           sudo pacman -S base-devel cmake"
        warn "Install them if you want to compile locally (e.g. for CUDA/Metal GPU support)."
    fi
fi

# ---------------------------------------------------------------------------
# 4. Network: the first install needs to reach PyPI
# ---------------------------------------------------------------------------
check_network() {
    echo "Checking network access to PyPI..."
    if ! python3 - <<'PY' 2>/dev/null
import sys
import urllib.request
try:
    urllib.request.urlopen("https://pypi.org/simple/", timeout=8)
except Exception:
    sys.exit(1)
PY
    then
        error_exit "Cannot reach PyPI (https://pypi.org). Check your internet connection and any proxy settings, then run this script again."
    fi
}

# ---------------------------------------------------------------------------
# 5. Dependency check: is everything from requirements.txt installed?
# ---------------------------------------------------------------------------
echo "Verifying dependencies..."
MISSING_DEPS="$(python - <<'PY'
import importlib.metadata
import re

def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()

installed = {
    normalize(dist.metadata.get("Name", ""))
    for dist in importlib.metadata.distributions()
}

missing = []
with open("requirements.txt", encoding="utf-8") as fh:
    for raw in fh:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name = re.split(r"[<>=!~;\[ ]", line, maxsplit=1)[0].strip()
        if name and normalize(name) not in installed:
            missing.append(name)
print(", ".join(missing))
PY
)"

if [ -n "$MISSING_DEPS" ]; then
    echo "Missing dependencies: $MISSING_DEPS"
    check_network
    echo "Installing dependencies..."

    # Always use abetlen's prebuilt wheel index: llama-cpp-python has no PyPI
    # wheel on Linux, so without it pip would try to compile it from source and
    # fail on machines without a C toolchain. Packages that already ship PyPI
    # wheels (PySide6, numpy, ...) are unaffected by this extra index.
    if ! python -m pip install --disable-pip-version-check -r requirements.txt \
        --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
        >/tmp/gguf_pip_install.log 2>&1; then
        echo "Error: dependency installation failed." >&2
        echo "Common causes:" >&2
        echo "  - Missing build tools on Linux (see the warning above; install build-essential cmake)" >&2
        echo "  - No network access to PyPI" >&2
        echo "  - Python version not supported by a dependency" >&2
        echo "Full pip output is in /tmp/gguf_pip_install.log" >&2
        exit 1
    fi
else
    echo "All dependencies are installed."
fi

# ---------------------------------------------------------------------------
# 6. Launch the application
# ---------------------------------------------------------------------------
echo "Starting GGUF Loader..."
python main.py || error_exit "Failed to start the application. If you are on a headless machine (no display), run it on a machine with a desktop environment."

# Deactivate virtual environment when done
deactivate
