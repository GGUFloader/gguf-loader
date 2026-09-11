#!/bin/bash
# Build script for creating GGUF Loader executable on Linux WITH GPU (CUDA)
# Requires: NVIDIA driver ≥ 550 on the host; CUDA runtime libs are pip-installed
# into the venv (nvidia-cuda-runtime-cu12, nvidia-cublas-cu12).

set -e
cd "$(dirname "$0")/.."

echo "========================================"
echo "GGUF Loader - Linux GPU (CUDA) Builder"
echo "WITH ADDON SUPPORT (Floating Chat)"
echo "========================================"
echo

# ---------- 1. venv --------------------------------------------------
if [ ! -f ".venv_linux/bin/activate" ]; then
    echo "[1/5] Creating Linux venv..."
    python3 -m venv .venv_linux
    source .venv_linux/bin/activate
    pip install --upgrade pip
else
    echo "[1/5] Using existing Linux venv..."
    source .venv_linux/bin/activate
fi

# ---------- 2. CUDA wheel + pip deps ---------------------------------
echo
echo "[2/5] Installing llama-cpp-python CUDA wheel + dependencies..."
pip install llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

# CUDA runtime libraries that llama_cpp links against at load time.
# These are NOT bundled by the llama_cpp wheel itself; PyInstaller needs
# them on disk so dependency analysis can bundle them.
pip install nvidia-cuda-runtime-cu12 nvidia-cublas-cu12

# Copy CUDA runtime .so files into llama_cpp/lib so PyInstaller's
# hook-llama_cpp.py picks them up as binaries (not duplicates).
python3 - <<'PY'
import importlib.util, os, shutil, site
spec = importlib.util.find_spec('llama_cpp')
if spec is None:
    raise SystemExit("llama_cpp not installed")
dst = os.path.join(os.path.dirname(spec.origin), 'lib')
sp = site.getsitepackages()[0]
copies = [
    ('cuda_runtime', 'libcudart.so.12'),
    ('cublas',       'libcublas.so.12'),
    ('cublas',       'libcublasLt.so.12'),
]
os.makedirs(dst, exist_ok=True)
for pkg, name in copies:
    src = os.path.join(sp, 'nvidia', pkg, 'lib', name)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"Copied {name} -> llama_cpp/lib/")
    else:
        print(f"WARNING: {src} not found")
PY

# Install remaining project deps (skip llama-cpp-python, already installed)
pip install pyinstaller psutil fastapi uvicorn pydantic \
    langgraph langgraph-checkpoint-sqlite langchain-core \
    2>/dev/null || true

# ---------- 3. Frontend build check ----------------------------------
echo
echo "[3/5] Checking frontend..."
if [ ! -d "frontend/dist" ]; then
    echo "WARNING: frontend/dist not found. Run 'cd frontend && npm run build' first."
fi

# ---------- 4. Clean + build -----------------------------------------
echo
echo "[4/5] Cleaning previous builds..."
rm -rf build
rm -f dist/GGUFLoader_WithAddons_GPU

echo
echo "[5/5] Building GPU executable (GGUFLOADER_CUDA=1)..."
GGUFLOADER_CUDA=1 pyinstaller build_exe.spec --noconfirm

# ---------- 5. Rename ------------------------------------------------
VERSION=$(python3 -c "from ggufloader._version import __version__; print(__version__)" 2>/dev/null || echo "unknown")
FINAL_NAME="GGUFLoader_v${VERSION}_linux_x86_64_CUDA"

if [ -f "dist/GGUFLoader_WithAddons_GPU" ]; then
    mv "dist/GGUFLoader_WithAddons_GPU" "dist/${FINAL_NAME}"
    echo
    echo "========================================"
    echo "BUILD SUCCESSFUL!"
    echo "========================================"
    echo
    echo "GPU binary: dist/${FINAL_NAME}"
    echo
    echo "Note: this binary bundles the CUDA runtime but still needs"
    echo "an NVIDIA driver (≥ 550) on the target machine."
    echo
else
    echo
    echo "========================================"
    echo "BUILD FAILED!"
    echo "========================================"
    exit 1
fi
