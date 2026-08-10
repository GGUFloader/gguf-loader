"""
UI package - Presentation layer for GGUF Loader.

- MainWindow: application composition root (addon-compatible API).
- SettingsSidebar / ChatPanel: focused UI panels.
- ThemeMixin: dark/light theming.
"""

from .main_window import MainWindow
from .theme import ThemeMixin

__all__ = ["MainWindow", "ThemeMixin"]
