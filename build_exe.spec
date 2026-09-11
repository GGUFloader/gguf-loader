# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for GGUF Loader application.

The installer bundles exactly three things:
  1. The Python backend (FastAPI + llama.cpp + LangGraph agent)
  2. The built React UI (frontend/dist)
  3. The Electron runtime + standalone launcher (native window)

The legacy PySide6 desktop UI (ggufloader/ui, widgets, services, addons,
AddonManager) is deliberately excluded: the product UI is the React app in
Electron, so no Qt code or DLLs ship in the installer.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get the current directory
current_dir = os.path.abspath('.')

# GPU (CUDA) vs CPU-only bundle. The release workflow sets GGUFLOADER_CUDA=1
# for the GPU build and installs the CUDA wheel of llama-cpp-python; the
# default (unset/0) is the small CPU-only bundle. The llama_cpp hook reads
# the same variable - keep them in sync.
INCLUDE_CUDA = os.environ.get('GGUFLOADER_CUDA', '0').lower() in ('1', 'true', 'yes')
print(f"Build mode: {'GPU (CUDA)' if INCLUDE_CUDA else 'CPU-only'}")

# Find llama_cpp library path
llama_cpp_lib_path = None
try:
    import llama_cpp
    llama_cpp_dir = os.path.dirname(llama_cpp.__file__)
    llama_cpp_lib_path = os.path.join(llama_cpp_dir, 'lib')
    print(f"Found llama_cpp lib at: {llama_cpp_lib_path}")
except Exception as e:
    print(f"Warning: Could not find llama_cpp lib: {e}")

# Guard: a CPU-only bundle MUST be built from the CPU wheel.
#
# The CUDA wheel's llama.dll (-> ggml.dll) has a hard load-time dependency on
# ggml-cuda.dll: stripping it produces an exe whose `from llama_cpp import
# Llama` fails with FileNotFoundError ("or one of its dependencies"), so the
# FastAPI backend never starts and the window shows no UI. Measured on
# llama-cpp-python 0.3.34 / Windows: LoadLibraryExW(llama.dll) returns
# ERROR_MOD_NOT_FOUND (126) without ggml-cuda.dll and succeeds with it.
# Refusing here is far better than shipping an exe that crashes on launch.
if llama_cpp_lib_path and os.path.isdir(llama_cpp_lib_path):
    _cuda_libs = sorted(
        f for f in os.listdir(llama_cpp_lib_path)
        if 'cuda' in f.lower() or 'cublas' in f.lower()
    )
    if _cuda_libs and not INCLUDE_CUDA:
        raise SystemExit(
            "ERROR: the installed llama-cpp-python wheel ships CUDA libraries "
            f"({', '.join(_cuda_libs)}).\n"
            "A CPU-only bundle would have to strip them, but this wheel's "
            "llama.dll cannot load without ggml-cuda.dll, so the exe would "
            "crash at startup (no UI).\n\n"
            "Either install the CPU wheel first:\n"
            "    pip install llama-cpp-python==0.3.34 --force-reinstall\n"
            "or build the GPU bundle:\n"
            "    set GGUFLOADER_CUDA=1 && pyinstaller build_exe.spec"
        )

# Collect all data files and binaries
datas = []
binaries = []

datas += [
    ('icon.ico', '.'),
    # Model family profiles: ggufloader.core.llm.model_profiles resolves this
    # relative to its module path (ggufloader/config/), so keep that layout.
    ('ggufloader/config/model_families.json', 'ggufloader/config'),
]

# Bundle the built React frontend. The frozen app serves it through the
# FastAPI backend (ggufloader.api.app mounts PROJECT_ROOT/frontend/dist),
# so keep the frontend/dist/... layout inside the bundle.
# Bundle the Electron runtime so the app opens in a native window instead
# of a browser. The standalone launcher (electron/dist/standalone.js) just
# opens a BrowserWindow to the already-running backend on localhost:8000.
electron_dist = os.path.join(current_dir, 'electron', 'node_modules', 'electron', 'dist')
electron_app = os.path.join(current_dir, 'electron', 'dist')
# Windows only: the Linux binary intentionally keeps its browser fallback, and
# a checkout whose electron/node_modules was populated on Windows (as this dev
# machine's is) would otherwise bundle a Windows electron.exe into the Linux
# build - hundreds of MB of dead weight that can never launch there.
if sys.platform == 'win32' and os.path.isdir(electron_dist) and os.path.isfile(os.path.join(electron_dist, 'electron.exe')):
    # Bundle the entire Electron dist directory (exe, DLLs, .pak, resources/, locales/)
    for root, _dirs, files in os.walk(electron_dist):
        for fname in files:
            src = os.path.join(root, fname)
            dest = os.path.relpath(root, electron_dist)
            if dest == '.':
                dest = 'electron'
            else:
                dest = os.path.join('electron', dest)
            binaries.append((src, dest))
    # Standalone launcher app (standalone.js, preload.js, package.json)
    for fname in ('standalone.js', 'preload.js', 'package.json'):
        src = os.path.join(electron_app, fname)
        if os.path.isfile(src):
            datas.append((src, 'electron'))
    print(f"Bundled Electron runtime from {electron_dist}")
else:
    print(f"WARNING: Electron not found at {electron_dist} - app will open in browser.")

# Bundle the built React frontend. The frozen app serves it through the
# FastAPI backend (ggufloader.api.app mounts PROJECT_ROOT/frontend/dist),
# so keep the frontend/dist/... layout inside the bundle.
frontend_dist = os.path.join(current_dir, 'frontend', 'dist')
if os.path.isdir(frontend_dist):
    for root, _dirs, files in os.walk(frontend_dist):
        for fname in files:
            src = os.path.join(root, fname)
            dest = os.path.relpath(root, current_dir)
            datas.append((src, dest))
    print(f"Bundled React frontend from {frontend_dist}")
else:
    print(f"WARNING: frontend/dist not found at {frontend_dist} - "
          "the exe will have no web UI. Run 'npm run build' in frontend/ first.")

# Collect llama_cpp lib files. For CPU-only builds NEVER add the whole
# directory: that drags in ggml-cuda.dll (~950MB) plus its cublas/cublasLt
# runtime dependencies (~790MB more). Add file-by-file and skip anything
# CUDA. GPU builds (GGUFLOADER_CUDA=1) keep every file - ggml-cuda links
# against cublas at load time.
#
# Windows-only: on Linux the .so files are already collected as proper
# binaries by hook-llama_cpp.py (collect_all + collect_dynamic_libs); adding
# them again here as "datas" would duplicate every library in the bundle.
if sys.platform == 'win32' and llama_cpp_lib_path and os.path.exists(llama_cpp_lib_path):
    for file in os.listdir(llama_cpp_lib_path):
        if not INCLUDE_CUDA and ('cuda' in file.lower() or 'cublas' in file.lower()):
            print(f"Skipped CUDA file (size reduction): {file}")
            continue
        file_path = os.path.join(llama_cpp_lib_path, file)
        if file.lower().endswith('.dll'):
            binaries.append((file_path, 'llama_cpp/lib'))
            print(f"Added binary: {file}")
        elif os.path.isfile(file_path):
            datas.append((file_path, 'llama_cpp/lib'))
            print(f"Added llama_cpp data file: {file}")


# Some Python distributions (uv-managed standalone builds) keep OpenSSL's
# libssl-3-x64.dll / libcrypto-3-x64.dll next to _ssl.pyd in the stdlib DLLs
# directory; PyInstaller's binary analysis can miss them there, which breaks
# `import ssl` (and therefore uvicorn) in the frozen app. Add them explicitly
# when present - harmless on python.org installs where the same files exist.
for _name in ('libssl-3-x64.dll', 'libcrypto-3-x64.dll'):
    _p = os.path.join(sys.base_prefix, 'DLLs', _name)
    if os.path.exists(_p):
        binaries.append((_p, '.'))
        print(f'Added OpenSSL runtime: {_p}')


# Collect hidden imports - be explicit about all modules. No PySide6: the
# Python desktop UI is gone, the React/Electron UI is the only one.
hiddenimports = [
    # AI/ML modules
    'llama_cpp',

    # Utility modules
    'psutil',

    # Application modules (all nested inside the ggufloader package)
    'ggufloader',
    'ggufloader._version',
    'ggufloader.resource_manager',
    'ggufloader.config',
    'ggufloader.utils',
    'ggufloader.main',

    # Core package
    'ggufloader.core',
    'ggufloader.core.__init__',
    'ggufloader.core.llm',
    'ggufloader.core.llm.model_backend',
    'ggufloader.core.llm.prompt_builder',
    'ggufloader.core.llm.__init__',
    'ggufloader.core.agent',
    'ggufloader.core.agent.agent_engine',
    'ggufloader.core.agent.tool_registry',
    'ggufloader.core.agent.__init__',

    # Search (Find Paragraph) + text extraction
    'ggufloader.core.search',
    'ggufloader.core.search.paragraph_search',
    'ggufloader.core.search.planner',
    'ggufloader.core.agent.text_extract',
    'ggufloader.core.engine',
    'ggufloader.core.engine.protocol',
    'ggufloader.core.engine.llama_cpp_engine',
    'ggufloader.core.engine.langchain_adapter',

    # Web server stack: the default React UI is served by FastAPI/uvicorn
    # inside the frozen app. These used to be excluded (Qt-only era) - they
    # must be collected now or the exe starts with no UI at all.
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'websockets',
    'anyio',
]

# Collect lazy submodules so frozen imports never fail at runtime.
for _pkg in ('uvicorn', 'websockets', 'anyio'):
    hiddenimports += collect_submodules(_pkg)

# The React UI backend (ggufloader.api.*) is loaded by uvicorn through the
# import string "ggufloader.api.app:create_app" - invisible to static
# analysis. Collect the whole ggufloader package (including api routes and
# websocket handlers) so the frozen server can import it. The legacy
# PySide6 UI packages (ui, widgets, services, addons, addon_manager) are
# filtered out - they import PySide6, which this bundle never ships.
_QT_ONLY_PREFIXES = (
    'ggufloader.ui',
    'ggufloader.widgets',
    'ggufloader.services',
    'ggufloader.addons',
    'ggufloader.addon_manager',
)
hiddenimports += [
    m for m in collect_submodules('ggufloader')
    if not m.startswith(_QT_ONLY_PREFIXES)
]

# LangGraph/LangChain and pydantic are imported through the agent graph;
# collect all their submodules so lazy imports never fail in the frozen app.
for _pkg in ('langgraph', 'langchain_core', 'pydantic', 'pydantic_core'):
    hiddenimports += collect_submodules(_pkg)


# Windows-specific imports
if sys.platform == 'win32':
    try:
        hiddenimports += ['win32api', 'win32con', 'win32gui', 'pywintypes']
    except:
        pass

a = Analysis(
    ['main.py'],  # Single application entry point
    pathex=[current_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[os.path.join(current_dir, 'build_hooks')],  # Use hooks from build_hooks directory
    hooksconfig={},
    runtime_hooks=[os.path.join(current_dir, 'build_hooks', 'runtime_hook_llama.py')],
    excludes=[
        # Legacy PySide6 desktop UI - the product UI is the React app in
        # Electron, so Qt never ships in the installer. Excluding the whole
        # framework (plus the Qt-era ggufloader packages that import it)
        # keeps Qt and its ~300-400MB of DLLs out even if a stray import
        # edge tries to pull it back in.
        'PySide6', 'shiboken6',
        'ggufloader.addon_manager',
        'ggufloader.ui',
        'ggufloader.widgets',
        'ggufloader.services',
        'ggufloader.addons',

        # GUI frameworks we never need
        'tkinter', 'tk', 'tcl', '_tkinter',

        # Scientific/data packages (if not used)
        'matplotlib', 'scipy', 'IPython', 'notebook', 'jupyter',

        # Testing frameworks
        'pytest', 'unittest', 'nose',

        # Documentation tools
        'sphinx', 'docutils',

        # PyPDF2 is unused (PDF extraction is stdlib); pydantic must NOT be
        # excluded - langgraph/langchain-core require it.
        'PyPDF2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PyInstaller's binary-dependency analysis walks the PE import table of
# llama.dll and pulls in ggml-cuda.dll (~900MB) plus cublas deps
# automatically - our hook filters can't stop that. Filter a.binaries here,
# after Analysis, so CPU builds actually stay CPU-only.
if not INCLUDE_CUDA:
    def _is_cuda_binary(entry):
        return any(('cuda' in str(part).lower() or 'cublas' in str(part).lower())
                   for part in entry[:2])
    before = len(a.binaries)
    a.binaries = TOC([b for b in a.binaries if not _is_cuda_binary(b)])
    print(f"Post-analysis CUDA filter: removed {before - len(a.binaries)} "
          f"of {before} binaries")

# Prune dead weight that survives Analysis (this is what keeps the CUDA exe
# from ballooning past its content):
#   - llama_cpp/lib/*.lib + llama.lib: MSVC link-time artifacts, useless at
#     runtime (~22MB).
#   - libcrypto/libssl resolved from Git for Windows' mingw64 directory:
#     Python's own copies are already collected; the Git duplicates (~6MB)
#     are a PATH-analysis accident and must never ship.
#   - Qt DLLs/.qm translations no longer apply: PySide6 is excluded above,
#     so no Qt files ever enter the graph.
import re

_SIZE_DROP_DATA = re.compile(r'\.(qm|lib)$', re.IGNORECASE)

def _from_mingw(entry):
    return 'mingw64' in str(entry[1]).lower()

_before = (len(a.binaries), len(a.datas))
a.binaries = TOC([b for b in a.binaries if not _from_mingw(b)])
a.datas = TOC([
    d for d in a.datas
    if not _SIZE_DROP_DATA.search(os.path.basename(str(d[0])))
    and not _from_mingw(d)
])
print(f"Size prune: binaries {len(a.binaries)}/{_before[0]}, "
      f"datas {len(a.datas)}/{_before[1]}")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GGUFLoader_WithAddons_GPU' if INCLUDE_CUDA else 'GGUFLoader_WithAddons',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX off, deliberately: the onefile archive is already zlib-compressed,
    # so UPX saves almost nothing here (~1-2%) while adding a full extra
    # decompression pass on every launch (~900MB for the CUDA build),
    # tripping antivirus heuristics, and risking breakage on signed DLLs
    # (cublas/ggml-cuda). Dropping dead content above is the real saving.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    onefile=True,  # Create a single-file executable
)