"""
ChatTimeline - Visual timeline of conversation turns.

Shows a compact vertical timeline with:
- Turn number and role (user/assistant)
- Timestamp
- Preview text
- Click to scroll to that turn

Pattern from: ChatGPT sidebar + Discord message history.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class TurnCard(QFrame):
    """A single turn in the timeline."""

    turn_clicked = Signal(int)  # turn index

    def __init__(self, index: int, role: str, preview: str,
                 timestamp: str = "", parent=None):
        super().__init__(parent)
        self._index = index
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(48)
        self._build_ui(role, preview, timestamp)

    def _build_ui(self, role: str, preview: str, timestamp: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Role indicator dot
        dot = QLabel("●")
        color = "#60a5fa" if role == "user" else "#a78bfa"
        dot.setStyleSheet(f"color: {color}; font-size: 8px;")
        dot.setFixedWidth(12)
        layout.addWidget(dot)

        # Content
        content = QVBoxLayout()
        content.setSpacing(0)

        header = QHBoxLayout()
        role_label = QLabel(role.capitalize())
        role_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        role_label.setStyleSheet(f"color: {color};")
        header.addWidget(role_label)

        if timestamp:
            ts_label = QLabel(timestamp)
            ts_label.setStyleSheet("font-size: 8px; color: #6b7280;")
            header.addWidget(ts_label)
        header.addStretch()
        content.addLayout(header)

        preview_text = preview[:80] + ("…" if len(preview) > 80 else "")
        preview_label = QLabel(preview_text)
        preview_label.setStyleSheet("font-size: 9px; color: #9ca3af;")
        content.addWidget(preview_label)

        layout.addLayout(content, 1)

        # Hover effect
        self.setStyleSheet(
            "QFrame { background: transparent; border-radius: 4px; }"
            "QFrame:hover { background: #1f2937; }"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.turn_clicked.emit(self._index)


class ChatTimeline(QWidget):
    """Visual timeline of conversation turns.

    Usage:
        timeline = ChatTimeline()
        timeline.add_turn("user", "Hello!")
        timeline.add_turn("assistant", "Hi there! How can I help?")
        timeline.turn_clicked.connect(scroll_to_turn)
    """

    turn_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatTimeline")
        self._turns: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        header.setSpacing(6)

        title = QLabel("📜 Chat History")
        title.setObjectName("sectionEyebrow")
        title.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        header.addWidget(title)

        header.addStretch()

        self._count_label = QLabel("0 turns")
        self._count_label.setStyleSheet("font-size: 9px; color: #6b7280;")
        header.addWidget(self._count_label)

        layout.addLayout(header)

        # Scrollable timeline
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(300)

        self._container = QWidget()
        self._col = QVBoxLayout(self._container)
        self._col.setSpacing(2)
        self._col.setContentsMargins(0, 0, 0, 0)
        self._col.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

    def add_turn(self, role: str, preview: str, timestamp: str = "") -> None:
        """Add a turn to the timeline."""
        index = len(self._turns)
        self._turns.append({"role": role, "preview": preview, "timestamp": timestamp})

        card = TurnCard(index, role, preview, timestamp)
        card.turn_clicked.connect(self.turn_clicked.emit)
        self._col.insertWidget(self._col.count() - 1, card)

        self._count_label.setText(f"{len(self._turns)} turns")

    def clear(self) -> None:
        """Clear all turns."""
        self._turns.clear()
        while self._col.count() > 1:
            item = self._col.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._count_label.setText("0 turns")

    def update_last_turn(self, preview: str) -> None:
        """Update the preview text of the last turn."""
        if self._turns:
            self._turns[-1]["preview"] = preview
            # Rebuild last card
            if self._col.count() > 1:
                last_item = self._col.takeAt(self._col.count() - 2)
                if last_item.widget():
                    last_item.widget().setParent(None)
            turn = self._turns[-1]
            card = TurnCard(len(self._turns) - 1, turn["role"],
                           turn["preview"], turn.get("timestamp", ""))
            card.turn_clicked.connect(self.turn_clicked.emit)
            self._col.insertWidget(self._col.count() - 1, card)
