"""
PyInstaller hook for core package
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('core')
