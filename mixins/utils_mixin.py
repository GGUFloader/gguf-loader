"""
Utils Mixin - Utility functions and helper methods
"""
from PySide6.QtCore import QTimer


class UtilsMixin:
    """Mixin class for utility functions and helper methods"""

    def scroll_to_bottom(self):
        """Scroll chat to bottom"""
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))