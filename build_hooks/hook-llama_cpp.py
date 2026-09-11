"""
PyInstaller hook for llama_cpp package
Bundles either the CPU-only or the CUDA (GPU) build of the llama.cpp runtime,
selected by the GGUFLOADER_CUDA environment variable:

  GGUFLOADER_CUDA unset/0  -> CPU-only bundle (default, small)
  GGUFLOADER_CUDA=1        -> include ggml-cuda + cublas runtime (~2 GB extra)

CUDA runtime bundling (Linux): the cu124 Linux wheel ships libggml-cuda.so
but links against libcudart.so.12 / libcublas*.so.12 which it does NOT
bundle, so a frozen CUDA binary is only self-contained when those libs are in
it (users then need just the NVIDIA driver, no CUDA Toolkit install).
PyInstaller's dependency analysis bundles them automatically ONLY if the
build machine can resolve them (GitHub runners ship CUDA; a bare machine
does not). To build deterministically on any machine, install the CUDA
runtime pip packages and copy their libs next to the wheel's own libs so
llama_cpp imports and the analysis picks each lib up exactly once:

  pip install -r requirements.txt \
      --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 \
      nvidia-cuda-runtime-cu12 nvidia-cublas-cu12
  python - <<'PY'
  import importlib.util, os, shutil, site
  spec = importlib.util.find_spec('llama_cpp')
  dst = os.path.join(os.path.dirname(spec.origin), 'lib')
  sp = site.getsitepackages()[0]
  for pkg, name in (('cuda_runtime', 'libcudart.so.12'),
                    ('cublas', 'libcublas.so.12'),
                    ('cublas', 'libcublasLt.so.12')):
      shutil.copy2(os.path.join(sp, 'nvidia', pkg, 'lib', name), dst)
  PY

Do NOT add those libs to this hook's ``binaries`` output: dependency
analysis would then bundle them a second time under their own paths,
tripling the multi-hundred-MB cublas libs in the archive.
"""
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs
import os

# Set by the release workflow / build scripts. "1" = GPU (CUDA) bundle.
INCLUDE_CUDA = os.environ.get("GGUFLOADER_CUDA", "0").lower() in ("1", "true", "yes")

# Collect all llama_cpp files
datas, binaries, hiddenimports = collect_all('llama_cpp')

# Explicitly collect dynamic libraries
binaries += collect_dynamic_libs('llama_cpp')

# collect_all/collect_dynamic_libs pull EVERYTHING, including the ~900MB CUDA
# runtime plus its cublas dependencies. For CPU-only bundles drop any CUDA
# entry (binary or data). Match both 'cuda' and 'cublas' - the cublas runtime
# dlls don't say 'cuda'. For CUDA bundles keep everything (ggml-cuda needs
# its cublas DLLs at runtime).
def _cuda_entry(entry):
    # Entries are (source_path, dest, [type]) tuples - the source path is the
    # first element; check both leading elements to stay shape-agnostic.
    return any(('cuda' in str(part).lower() or 'cublas' in str(part).lower())
               for part in entry[:2])

if INCLUDE_CUDA:
    print("[Hook] GGUFLOADER_CUDA=1: keeping CUDA runtime in bundle (GPU build)")
else:
    binaries = [b for b in binaries if not _cuda_entry(b)]
    datas = [d for d in datas if not _cuda_entry(d)]
    print(f"[Hook] CUDA-filtered: {len(binaries)} binaries, {len(datas)} datas")

# Add the lib directory explicitly (CPU-only, exclude CUDA).
# Windows-only: on Linux the .so libraries are already collected as binaries
# by collect_all/collect_dynamic_libs above; listing them as datas would
# duplicate every library and break loader semantics (data files are not
# marked executable).
import sys
try:
    import llama_cpp
    llama_cpp_dir = os.path.dirname(llama_cpp.__file__)
    lib_dir = os.path.join(llama_cpp_dir, 'lib')

    if sys.platform == 'win32' and os.path.exists(lib_dir):
            # For CPU-only bundles add CPU files only (CUDA libs are huge).
            # CUDA bundles add everything: ggml-cuda links against cublas at
            # load time and fails to start without it.
            for file in os.listdir(lib_dir):
                # Skip CUDA files in CPU bundles. Match 'cublas' too.
                if not INCLUDE_CUDA and ('cuda' in file.lower() or 'cublas' in file.lower()):
                    print(f"[Hook] Skipped CUDA file (size reduction): {file}")
                    continue
                
                file_path = os.path.join(lib_dir, file)
                if os.path.isfile(file_path):
                    datas.append((file_path, 'llama_cpp/lib'))
                    print(f"[Hook] Added llama_cpp file: {file}")
except Exception as e:
    print(f"[Hook] Warning: Could not collect llama_cpp lib files: {e}")

# Ensure all submodules are imported
hiddenimports += [
    'llama_cpp.llama',
    'llama_cpp.llama_cpp',
    'llama_cpp._ctypes_extensions',
]
