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
    ('addons/floating_chat', 'addons/floating_chat'),  # Only include floating_chat, not agentic_chatbot
    ('docs', 'docs'),
    ('core', 'core'),  # Include the core module directory
]

# Add llama_cpp lib folder if found
if llama_cpp_lib_path and os.path.exists(llama_cpp_lib_path):
    datas.append((llama_cpp_lib_path, 'llama_cpp/lib'))
    print(f"Added llama_cpp/lib to datas")

# Collect binaries (DLL files) - CPU only, skip CUDA for size reduction
binaries = []
if llama_cpp_lib_path and os.path.exists(llama_cpp_lib_path):
    # Add only CPU DLL files, skip CUDA (saves 400-500MB)
    for file in os.listdir(llama_cpp_lib_path):
        if file.endswith('.dll'):
            # Skip CUDA files to reduce size
            if 'cuda' in file.lower():
                print(f"Skipped CUDA binary (size reduction): {file}")
                continue
            dll_path = os.path.join(llama_cpp_lib_path, file)
            binaries.append((dll_path, 'llama_cpp/lib'))
            print(f"Added binary: {file}")


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
    
    # Application modules
    'addon_manager',
    'resource_manager',
    'config',
    'utils',

    # Models package
    'models',
    'models.model_loader',
    'models.chat_generator',
    'models.__init__',

    # UI package
    'ui',
    'ui.ai_chat_window',
    'ui.apply_style',
    'ui.__init__',

    # Widgets package
    'widgets',
    'widgets.addon_sidebar',
    'widgets.chat_bubble',
    'widgets.collapsible_widget',
    'widgets.__init__',

    # Mixins package
    'mixins',
    'mixins.addon_mixin',
    'mixins.chat_handler_mixin',
    'mixins.event_handler_mixin',
    'mixins.model_handler_mixin',
    'mixins.ui_setup_mixin',
    'mixins.utils_mixin',
    'mixins.agent_mode_mixin',
    'mixins.__init__',

    # Core agent package
    'core',
    'core.agent',
    'core.agent.simple_agent',
    'core.agent.enterprise_agent',
    'core.agent.loop_engine',
    'core.agent.planner',
    'core.agent.task_executor',
    'core.agent.tool_executor',
    'core.agent.decision_engine',
    'core.agent.task_by_task_engine',
    'core.agent.agentic_loop',
    'core.agent.orchestrator',
    'core.agent.__init__',
    'core.__init__',
    
    # Addons package
    'addons',
    'addons.__init__',
    'addons.floating_chat',
    'addons.floating_chat.main',
    'addons.floating_chat.chat_window',
    'addons.floating_chat.floating_button',
    'addons.floating_chat.status_widget',
    'addons.floating_chat.__init__',
]

# Windows-specific imports
if sys.platform == 'win32':
    try:
        hiddenimports += ['win32api', 'win32con', 'win32gui', 'pywintypes']
    except:
        pass

a = Analysis(
    ['gguf_loader_main.py'],  # Use the version with addon support
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
        
        # Heavy agent dependencies (saves ~300MB)
        'pydantic', 'pydantic_core', 'PyPDF2',
        'core', 'core.agent',
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
