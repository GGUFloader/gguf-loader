"""
DisclosureRow - Reusable expand/collapse component with icon.

Inspired by DeepSeek Harness's DisclosureRow which provides a consistent
expand/collapse pattern used across reasoning rows, command cards, and
tool call displays.

Source: deepseek-harness/packages/client/ui-primitives/DisclosureRow
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)


class DisclosureRow(QFrame):
    """Reusable expand/collapse row with leading icon, title, and summary.

    Usage:
        row = DisclosureRow(
            icon_text="💭",
            title="Thinking",
            summary="Analyzing code structure...",
        )
        row.set_content(some_widget)  # content shown when expanded
        layout.addWidget(row)

    Signals:
        toggled(bool): Emitted when expanded/collapsed
    """

    toggled = Signal(bool)

    def __init__(
        self,
        icon_text: str = "▸",
        title: str = "",
        summary: str = "",
        expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._expanded = expanded
        self._icon_text = icon_text
        self._title_text = title
        self._summary_text = summary
        self._content_widget: Optional[QWidget] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header row (clickable)
        self._header = QFrame()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet(
            "QFrame { background: transparent; } "
            "QFrame:hover { background: rgba(128,128,128,0.08); }"
        )
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(6)

        # Chevron
        self._chevron = QLabel(self._get_chevron())
        self._chevron.setFixedWidth(14)
        self._chevron.setStyleSheet("font-size: 10px; color: #94a3b8;")
        header_layout.addWidget(self._chevron)

        # Icon
        self._icon = QLabel(self._icon_text)
        self._icon.setFixedWidth(18)
        self._icon.setStyleSheet("font-size: 12px;")
        header_layout.addWidget(self._icon)

        # Title
        self._title = QLabel(self._title_text)
        self._title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header_layout.addWidget(self._title)

        # Summary (shown when collapsed)
        self._summary = QLabel(self._summary_text)
        self._summary.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self._summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._summary.setWordWrap(False)
        header_layout.addWidget(self._summary, 1)

        header_layout.addStretch()
        self._header.mousePressEvent = self._toggle
        layout.addWidget(self._header)

        # Content (shown when expanded)
        self._content_frame = QFrame()
        self._content_frame.setVisible(self._expanded)
        self._content_layout = QVBoxLayout(self._content_frame)
        self._content_layout.setContentsMargins(32, 4, 8, 8)
        self._content_layout.setSpacing(0)
        layout.addWidget(self._content_frame)

    def _get_chevron(self) -> str:
        return "▾" if self._expanded else "▸"

    def _toggle(self, event=None) -> None:
        self._expanded = not self._expanded
        self._chevron.setText(self._get_chevron())
        self._content_frame.setVisible(self._expanded)
        self.toggled.emit(self._expanded)

    def set_content(self, widget: QWidget) -> None:
        """Set the content widget shown when expanded."""
        if self._content_widget is not None:
            self._content_widget.setParent(None)
        self._content_widget = widget
        self._content_layout.addWidget(widget)

    def set_summary(self, text: str) -> None:
        """Update the summary text."""
        self._summary_text = text
        self._summary.setText(text)

    def set_title(self, text: str) -> None:
        """Update the title text."""
        self._title_text = text
        self._title.setText(text)

    def set_expanded(self, expanded: bool) -> None:
        """Programmatically expand/collapse."""
        if self._expanded != expanded:
            self._toggle()

    @property
    def is_expanded(self) -> bool:
        return self._expanded
