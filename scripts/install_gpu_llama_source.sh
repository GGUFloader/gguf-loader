#!/bin/bash
# GGUF Loader - Build llama-cpp-python from source with GPU support (Linux/macOS)
# Mirrors scripts/install_gpu_llama_source.bat for Windows.
# Requires a C++ compiler and CMake; CUDA Toolkit on Linux (or Xcode CLT on macOS).

# Change to the project root so relative paths work from anywhere
cd "$(dirname "$0")/.."

error_exit() {
    echo "Error: $1" >&2
    exit 1
}

echo "Building llama-cpp-python from source with GPU support..."
echo "This requires a C++ compiler (gcc/clang), CMake, and the CUDA Toolkit (Linux)."
echo

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
    echo "Virtual environment activated"
else
    error_exit "Virtual environment not found at .venv/bin/activate. Create one with: python3 -m venv .venv"
fi

echo
echo "Uninstalling existing version..."
pip uninstall -y llama-cpp-python || error_exit "Failed to uninstall llama-cpp-python"

echo
echo "Building from source with GPU support (this may take 5-10 minutes)..."
if [ "$(uname -s)" = "Darwin" ]; then
    # macOS: no NVIDIA/CUDA - use Apple's Metal backend instead
    export CMAKE_ARGS="-DGGML_METAL=on"
else
    export CMAKE_ARGS="-DGGML_CUDA=on"
fi
export FORCE_CMAKE=1

pip install llama-cpp-python --no-cache-dir --force-reinstall \
    || error_exit "Build failed. Check the compiler/CMake/CUDA errors above."

echo
echo "Build complete!"
echo
echo "To verify GPU support, run: python scripts/verify_gpu_support.py"
