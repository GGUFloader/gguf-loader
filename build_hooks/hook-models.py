"""
PyInstaller hook for models package
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('models')
