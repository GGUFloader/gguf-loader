"""
AttachmentPreview - Inline preview of attached files.

Shows attached file chips with:
- File name and size
- Preview of content (first few lines)
- Remove button
- Syntax highlighting for code files

Pattern from: GitHub issue attachments + Discord file previews.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


def _file_icon(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    icons = {
        ".py": "🐍", ".js": "📜", ".ts": "📜", ".jsx": "⚛️", ".tsx": "⚛️",
        ".rs": "🦀", ".go": "🔵", ".java": "☕", ".c": "⚙️", ".cpp": "⚙️",
        ".h": "⚙️", ".rb": "💎", ".php": "🐘",
        ".html": "🌐", ".css": "🎨", ".scss": "🎨",
        ".json": "📋", ".yaml": "📋", ".yml": "📋", ".toml": "📋",
        ".md": "📝", ".txt": "📄", ".rst": "📄",
        ".sql": "🗃️", ".sh": "🖥️", ".bat": "🖥️",
        ".r": "📊", ".swift": "🍎", ".kt": "🟣",
    }
    return icons.get(ext, "📄")


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


class AttachmentChip(QFrame):
    """A single file attachment chip with preview."""

    removed = Signal(str)  # filename

    def __init__(self, filename: str, content: str = "",
                 file_path: str = "", parent=None):
        super().__init__(parent)
        self._filename = filename
        self._content = content
        self._file_path = file_path
        self.setObjectName("attachmentChip")
        self._expanded = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(6)

        icon = QLabel(_file_icon(self._filename))
        icon.setFont(QFont(FONT_FAMILY, 12))
        header.addWidget(icon)

        name = QLabel(self._filename)
        name.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        header.addWidget(name)

        if self._content:
            size_label = QLabel(f"{len(self._content)} chars")
            size_label.setStyleSheet("font-size: 9px; color: #6b7280;")
            header.addWidget(size_label)

        header.addStretch()

        # Expand/collapse button
        if self._content:
            self._toggle_btn = QPushButton("▼")
            self._toggle_btn.setFixedSize(18, 18)
            self._toggle_btn.setStyleSheet("border: none; font-size: 8px;")
            self._toggle_btn.clicked.connect(self._toggle_expand)
            header.addWidget(self._toggle_btn)

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setStyleSheet("border: none; font-size: 8px; color: #ef4444;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self._filename))
        header.addWidget(remove_btn)

        layout.addLayout(header)

        # Preview (hidden by default)
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFont(QFont("Consolas", 9))
        self._preview.setMaximumHeight(120)
        self._preview.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._preview.setStyleSheet("background: #1f2937; border: 1px solid #374151; border-radius: 4px;")
        # Show first 10 lines
        lines = self._content.split("\n")[:10]
        self._preview.setPlainText("\n".join(lines))
        self._preview.setVisible(False)
        layout.addWidget(self._preview)

        # Hover effect
        self.setStyleSheet(
            "QFrame#attachmentChip { background: #1f2937; border-radius: 6px; border: 1px solid #374151; }"
            "QFrame#attachmentChip:hover { border: 1px solid #4b5563; }"
        )

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self._preview.setVisible(self._expanded)
        self._toggle_btn.setText("▲" if self._expanded else "▼")


class AttachmentPreview(QWidget):
    """Container for multiple file attachment chips.

    Usage:
        preview = AttachmentPreview()
        preview.add_attachment("README.md", "# Hello\nWorld")
        preview.removed.connect(remove_file)
    """

    removed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("attachmentPreview")
        self._chips: dict[str, AttachmentChip] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        header.setSpacing(6)

        self._title = QLabel("📎 Attachments (0)")
        self._title.setObjectName("sectionEyebrow")
        self._title.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        header.addWidget(self._title)

        header.addStretch()

        self._clear_all_btn = QPushButton("Clear All")
        self._clear_all_btn.setStyleSheet("font-size: 9px; border: none; color: #ef4444;")
        self._clear_all_btn.clicked.connect(self.clear_all)
        header.addWidget(self._clear_all_btn)

        layout.addLayout(header)

        # Chips container
        self._chips_container = QWidget()
        self._chips_layout = QVBoxLayout(self._chips_container)
        self._chips_layout.setSpacing(4)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._chips_container)

        self.setVisible(False)

    def add_attachment(self, filename: str, content: str = "",
                       file_path: str = "") -> None:
        """Add a file attachment."""
        if filename in self._chips:
            return
        chip = AttachmentChip(filename, content, file_path)
        chip.removed.connect(self._remove_attachment)
        self._chips[filename] = chip
        self._chips_layout.addWidget(chip)
        self._update_title()
        self.setVisible(True)

    def _remove_attachment(self, filename: str) -> None:
        chip = self._chips.pop(filename, None)
        if chip:
            chip.setParent(None)
        self._update_title()
        if not self._chips:
            self.setVisible(False)
        self.removed.emit(filename)

    def clear_all(self) -> None:
        for chip in list(self._chips.values()):
            chip.setParent(None)
        self._chips.clear()
        self._update_title()
        self.setVisible(False)

    def _update_title(self) -> None:
        count = len(self._chips)
        self._title.setText(f"📎 Attachments ({count})")

    def get_attachments(self) -> dict[str, str]:
        """Return {filename: content} for all attachments."""
        return {name: chip._content for name, chip in self._chips.items()}
