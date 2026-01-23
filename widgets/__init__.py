"""
Widgets package - Contains all custom UI widgets

This package provides specialized widgets for the GGUF Loader application
including addon sidebar, chat bubbles, and collapsible widgets.
"""

from .addon_sidebar import AddonSidebar
from .chat_bubble import ChatBubble
from .collapsible_widget import CollapsibleWidget
from .feedback_dialog import FeedbackDialog

__all__ = [
    'AddonSidebar',
    'ChatBubble',
    'CollapsibleWidget',
    'FeedbackDialog'
]
