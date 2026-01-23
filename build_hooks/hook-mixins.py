"""
PyInstaller hook for mixins package
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('mixins')
