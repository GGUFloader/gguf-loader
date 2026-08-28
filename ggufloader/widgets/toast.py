"""
Toast - Non-blocking notification widget.

Appears at the bottom of the main window, auto-hides after a timeout.
Supports info, success, warning, error styles.

Pattern from: Android toast + GitHub notification banners.
"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class Toast(QWidget):
    """A temporary notification that auto-dismisses.

    Usage:
        Toast.show_info(parent, "Model loaded successfully")
        Toast.show_error(parent, "Failed to load model")
        Toast.show_success(parent, "Agent settings saved")
        Toast.show_warning(parent, "Context window almost full")
    """

    _current: Toast | None = None

    def __init__(self, parent: QWidget, message: str,
                 style: str = "info", duration_ms: int = 3000) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setFixedHeight(40)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self._duration = duration_ms
        self._build_ui(message, style)
        self._position()
        self._setup_timer()

    def _build_ui(self, message: str, style: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
        }
        colors = {
            "info": "#3b82f6",
            "success": "#22c55e",
            "warning": "#f59e0b",
            "error": "#ef4444",
        }
        bg_colors = {
            "info": "#1e3a5f",
            "success": "#14532d",
            "warning": "#78350f",
            "error": "#7f1d1d",
        }

        icon = QLabel(icons.get(style, "ℹ️"))
        icon.setFont(QFont(FONT_FAMILY, 12))
        layout.addWidget(icon)

        text = QLabel(message)
        text.setFont(QFont(FONT_FAMILY, 11))
        text.setStyleSheet(f"color: {colors.get(style, '#d1d5db')};")
        text.setWordWrap(True)
        layout.addWidget(text, 1)

        bg = bg_colors.get(style, "#1e3a5f")
        border = colors.get(style, "#3b82f6")
        self.setStyleSheet(
            f"background: {bg}; border: 1px solid {border}; border-radius: 6px;"
        )

    def _position(self) -> None:
        """Center at the bottom of the parent."""
        parent = self.parent()
        if parent is None:
            return
        pw = parent.width()
        self.setFixedWidth(min(pw - 40, 500))
        x = (pw - self.width()) // 2
        y = parent.height() - 70
        self.move(x, y)

    def _setup_timer(self) -> None:
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._duration)
        self._timer.timeout.connect(self._dismiss)
        self.show()
        self._timer.start()

    def _dismiss(self) -> None:
        self.setParent(None)
        Toast._current = None

    @classmethod
    def show_info(cls, parent: QWidget, message: str, duration_ms: int = 3000) -> Toast:
        return cls._show(parent, message, "info", duration_ms)

    @classmethod
    def show_success(cls, parent: QWidget, message: str, duration_ms: int = 3000) -> Toast:
        return cls._show(parent, message, "success", duration_ms)

    @classmethod
    def show_warning(cls, parent: QWidget, message: str, duration_ms: int = 4000) -> Toast:
        return cls._show(parent, message, "warning", duration_ms)

    @classmethod
    def show_error(cls, parent: QWidget, message: str, duration_ms: int = 5000) -> Toast:
        return cls._show(parent, message, "error", duration_ms)

    @classmethod
    def _show(cls, parent: QWidget, message: str, style: str,
              duration_ms: int) -> Toast:
        # Dismiss any existing toast
        if cls._current is not None:
            cls._current._dismiss()
        toast = cls(parent, message, style, duration_ms)
        cls._current = toast
        return toast
