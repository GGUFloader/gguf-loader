"""
UI package - Contains all user interface components

This package provides the main chat window and styling functionality
for the GGUF Loader application.
"""

from .ai_chat_window import AIChat
from .apply_style import ThemeMixin

__all__ = [
    'AIChat',
    'ThemeMixin'
]
