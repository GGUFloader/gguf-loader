"""
Custom PySide6 hook - only include modules we actually use
This overrides PyInstaller's default hook that includes everything
"""
from PyInstaller.utils.hooks import collect_submodules

# Only include the Qt modules we actually use
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui', 
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',  # Might be needed for some features
]

# Don't collect all submodules - only what we specified above
# This prevents PyInstaller from including QtWebEngine, Qt3D, QtCharts, etc.
