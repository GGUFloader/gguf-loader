"""
Widgets package - Contains all custom UI widgets

This package provides specialized widgets for the GGUF Loader application
including chat bubbles and the feedback dialog.
"""

from .chat_bubble import ChatBubble
from .feedback_dialog import FeedbackDialog

__all__ = [
    'ChatBubble',
    'FeedbackDialog'
]
