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
    ('addons', 'addons'),
    ('docs', 'docs'),
]

# Add llama_cpp lib folder if found
if llama_cpp_lib_path and os.path.exists(llama_cpp_lib_path):
    datas.append((llama_cpp_lib_path, 'llama_cpp/lib'))
    print(f"Added llama_cpp/lib to datas")

# Collect binaries (DLL files)
binaries = []
if llama_cpp_lib_path and os.path.exists(llama_cpp_lib_path):
    # Add all DLL files from llama_cpp/lib
    for file in os.listdir(llama_cpp_lib_path):
        if file.endswith('.dll'):
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
    'mixins.__init__',
    
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
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,      # Include binaries in single file
    a.zipfiles,      # Include zipfiles in single file
    a.datas,         # Include data files in single file
    [],
    name='GGUFLoader_WithAddons',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

# Note: COLLECT is not needed for one-file mode
# The single .exe will be in dist/ folder directly
