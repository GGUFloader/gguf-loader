"""
PyInstaller hook for addons package
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('addons')
