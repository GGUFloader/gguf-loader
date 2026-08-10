# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for GGUF Loader application
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get the current directory
current_dir = os.path.abspath('.')

# Find llama_cpp library path
llama_cpp_lib_path = None
try:
    import llama_cpp
    llama_cpp_dir = os.path.dirname(llama_cpp.__file__)
    llama_cpp_lib_path = os.path.join(llama_cpp_dir, 'lib')
    print(f"Found llama_cpp lib at: {llama_cpp_lib_path}")
except Exception as e:
    print(f"Warning: Could not find llama_cpp lib: {e}")

# Collect all data files
datas = [
    ('icon.ico', '.'),
    ('float.png', '.'),  # Floating chat button icon
    ('ggufloader/addons/floating_chat', 'ggufloader/addons/floating_chat'),  # Only include floating_chat
]

# Collect llama_cpp lib files - CPU only. NEVER add the whole directory:
# that drags in ggml-cuda.dll (~950MB) plus its cublas/cublasLt runtime
# dependencies (~790MB more). Add file-by-file and skip anything CUDA.
binaries = []
if llama_cpp_lib_path and os.path.exists(llama_cpp_lib_path):
    for file in os.listdir(llama_cpp_lib_path):
        if 'cuda' in file.lower() or 'cublas' in file.lower():
            print(f"Skipped CUDA file (size reduction): {file}")
            continue
        file_path = os.path.join(llama_cpp_lib_path, file)
        if file.lower().endswith('.dll'):
            binaries.append((file_path, 'llama_cpp/lib'))
            print(f"Added binary: {file}")
        elif os.path.isfile(file_path):
            datas.append((file_path, 'llama_cpp/lib'))
            print(f"Added llama_cpp data file: {file}")


# Collect hidden imports - be explicit about all modules
hiddenimports = [
    # Qt modules
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    
    # AI/ML modules
    'llama_cpp',
    
    # Utility modules
    'pyautogui',
    'pyperclip',
    'psutil',
    
    # Application modules (all nested inside the ggufloader package)
    'ggufloader',
    'ggufloader._version',
    'ggufloader.addon_manager',
    'ggufloader.resource_manager',
    'ggufloader.config',
    'ggufloader.utils',
    'ggufloader.main',

    # UI package
    'ggufloader.ui',
    'ggufloader.ui.main_window',
    'ggufloader.ui.sidebar_panel',
    'ggufloader.ui.chat_panel',
    'ggufloader.ui.agent_panel',
    'ggufloader.ui.theme',
    'ggufloader.ui.__init__',

    # Widgets package
    'ggufloader.widgets',
    'ggufloader.widgets.chat_bubble',
    'ggufloader.widgets.feedback_dialog',
    'ggufloader.widgets.__init__',

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

    # Services package
    'ggufloader.services',
    'ggufloader.services.model_service',
    'ggufloader.services.chat_service',
    'ggufloader.services.agent_service',
    'ggufloader.services.__init__',
    
    # Addons package
    'ggufloader.addons',
    'ggufloader.addons.__init__',
    'ggufloader.addons.floating_chat',
    'ggufloader.addons.floating_chat.main',
    'ggufloader.addons.floating_chat.chat_window',
    'ggufloader.addons.floating_chat.floating_button',
    'ggufloader.addons.floating_chat.status_widget',
    'ggufloader.addons.floating_chat.__init__',

    # Search (Find Paragraph) + text extraction
    'ggufloader.core.search',
    'ggufloader.core.search.paragraph_search',
    'ggufloader.core.search.planner',
    'ggufloader.core.agent.text_extract',
    'ggufloader.core.engine',
    'ggufloader.core.engine.protocol',
    'ggufloader.core.engine.llama_cpp_engine',
    'ggufloader.core.engine.langchain_adapter',
    'ggufloader.services.search_service',
    'ggufloader.ui.find_dialog',
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
        # GUI frameworks (we only need PySide6 Core/Gui/Widgets)
        'tkinter', 'tk', 'tcl', '_tkinter',
        
        # Unused PySide6 modules (saves ~300-400MB)
        'PySide6.QtWebEngine', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel', 'PySide6.QtWebSockets',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput', 'PySide6.Qt3DAnimation',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQml',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtHelp',
        'PySide6.QtDesigner', 'PySide6.QtUiTools',
        'PySide6.QtSvg', 'PySide6.QtSvgWidgets',
        'PySide6.QtXml', 'PySide6.QtPrintSupport',
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning',
        'PySide6.QtRemoteObjects', 'PySide6.QtScxml', 'PySide6.QtSensors',
        'PySide6.QtSerialPort', 'PySide6.QtTextToSpeech',
        
        # Web/server frameworks (not needed for desktop app)
        'uvicorn', 'websockets', 'fastapi', 'starlette',
        
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GGUFLoader_WithAddons',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    onefile=True,  # Create a single-file executable
)
