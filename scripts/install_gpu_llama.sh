#!/bin/bash
# GGUF Loader - Install GPU-enabled llama-cpp-python (Linux/macOS)
# Downloads a prebuilt CUDA wheel from abetlen's index. No compiler needed.

# Change to the project root so relative paths work from anywhere
cd "$(dirname "$0")/.."

error_exit() {
    echo "Error: $1" >&2
    exit 1
}

echo "Installing GPU-enabled llama-cpp-python..."
echo

# macOS has no NVIDIA/CUDA support, so CUDA wheels are unavailable. Exit
# BEFORE uninstalling anything, or the working CPU build would be destroyed.
if [ "$(uname -s)" = "Darwin" ]; then
    echo "Note: macOS has no NVIDIA/CUDA support, so CUDA wheels are unavailable."
    echo "      Use scripts/install_gpu_llama_source.sh for a Metal-accelerated build."
    exit 1
fi

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
    echo "Virtual environment activated"
else
    error_exit "Virtual environment not found at .venv/bin/activate. Create one with: python3 -m venv .venv"
fi

echo
echo "Uninstalling existing CPU version..."
pip uninstall -y llama-cpp-python || error_exit "Failed to uninstall llama-cpp-python"

echo
echo "Installing GPU version with CUDA support (prebuilt wheel)..."
pip install llama-cpp-python==0.3.34 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 \
    || error_exit "GPU install failed. Check your internet connection and try again later."

echo
echo "Installation complete!"
echo
echo "To verify GPU support, run: python scripts/verify_gpu_support.py"
