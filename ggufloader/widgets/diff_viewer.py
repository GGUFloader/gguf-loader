"""
DiffViewer - Side-by-side file change viewer.

Shows before/after content when the agent edits a file.
Supports:
- Side-by-side view (old | new)
- Unified view (git-style +/- lines)
- Syntax highlighting for code
- Line numbers
- Copy changed text

Pattern from: Aider diff display + GitHub PR diffs.
"""

from __future__ import annotations

import difflib
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


def _make_format(color: str, bold: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    return fmt


class DiffViewer(QWidget):
    """Side-by-side or unified diff viewer.

    Usage:
        viewer = DiffViewer()
        viewer.set_diff("old content", "new content", "path/to/file.py")
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("diffViewer")
        self._old_text = ""
        self._new_text = ""
        self._file_path = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        self._file_label = QLabel("")
        self._file_label.setObjectName("toolCardTitle")
        header.addWidget(self._file_label)

        header.addStretch()

        # View mode toggle
        self._side_btn = QPushButton("Side by Side")
        self._side_btn.setCheckable(True)
        self._side_btn.setChecked(True)
        self._side_btn.clicked.connect(lambda: self._set_view("side"))
        header.addWidget(self._side_btn)

        self._unified_btn = QPushButton("Unified")
        self._unified_btn.setCheckable(True)
        self._unified_btn.clicked.connect(lambda: self._set_view("unified"))
        header.addWidget(self._unified_btn)

        self._copy_btn = QPushButton("📋 Copy")
        self._copy_btn.clicked.connect(self._copy_diff)
        header.addWidget(self._copy_btn)

        layout.addLayout(header)

        # Stats
        self._stats_label = QLabel("")
        self._stats_label.setObjectName("mutedLabel")
        self._stats_label.setStyleSheet("font-size: 10px;")
        layout.addWidget(self._stats_label)

        # Content area
        self._content = QFrame()
        self._content.setObjectName("toolCard")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Side-by-side splitter
        self._splitter = QSplitter(Qt.Horizontal)
        self._old_editor = self._make_editor(read_only=True)
        self._new_editor = self._make_editor(read_only=True)
        self._splitter.addWidget(self._old_editor)
        self._splitter.addWidget(self._new_editor)
        self._splitter.setSizes([400, 400])
        content_layout.addWidget(self._splitter)

        # Unified view (hidden by default)
        self._unified_editor = self._make_editor(read_only=True)
        self._unified_editor.setVisible(False)
        content_layout.addWidget(self._unified_editor)

        layout.addWidget(self._content, 1)

    def _make_editor(self, read_only: bool = True) -> QTextEdit:
        editor = QTextEdit()
        editor.setReadOnly(read_only)
        editor.setFont(QFont("Consolas", 10))
        editor.setLineWrapMode(QTextEdit.NoWrap)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor.setObjectName("diffEditor")
        return editor

    def set_diff(self, old_text: str, new_text: str,
                 file_path: str = "") -> None:
        """Set the diff content and render both views."""
        self._old_text = old_text
        self._new_text = new_text
        self._file_path = file_path

        self._file_label.setText(f"📄 {file_path}" if file_path else "📄 Diff")

        # Calculate stats
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        added = sum(1 for line in difflib.unified_diff(old_lines, new_lines)
                    if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in difflib.unified_diff(old_lines, new_lines)
                      if line.startswith("-") and not line.startswith("---"))
        self._stats_label.setText(f"+{added} / -{removed} lines")

        self._render_side_by_side(old_lines, new_lines)
        self._render_unified(old_lines, new_lines)

    def _render_side_by_side(self, old_lines: list, new_lines: list) -> None:
        """Render side-by-side diff."""
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        old_text = QTextCursor(self._old_editor.document())
        old_text.movePosition(QTextCursor.Start)
        new_text = QTextCursor(self._new_editor.document())
        new_text.movePosition(QTextCursor.Start)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for line in old_lines[i1:i2]:
                    old_text.insertText(line + "\n")
                for line in new_lines[j1:j2]:
                    new_text.insertText(line + "\n")
            elif tag == "replace" or tag == "delete":
                for line in old_lines[i1:i2]:
                    old_text.setCharFormat(_make_format("#fca5a5"))
                    old_text.insertText("- " + line + "\n")
                for _ in range(j2 - j1):
                    new_text.setCharFormat(_make_format("#6b7280"))
                    new_text.insertText("  \n")
            elif tag == "insert":
                for _ in range(i2 - i1):
                    old_text.setCharFormat(_make_format("#6b7280"))
                    old_text.insertText("  \n")
                for line in new_lines[j1:j2]:
                    new_text.setCharFormat(_make_format("#86efac"))
                    new_text.insertText("+ " + line + "\n")

    def _render_unified(self, old_lines: list, new_lines: list) -> None:
        """Render unified diff (git-style)."""
        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile="old", tofile="new",
            lineterm="",
        ))
        cursor = QTextCursor(self._unified_editor.document())
        cursor.movePosition(QTextCursor.Start)

        for line in diff:
            if line.startswith("+++") or line.startswith("---"):
                cursor.setCharFormat(_make_format("#9ca3af", bold=True))
            elif line.startswith("+"):
                cursor.setCharFormat(_make_format("#86efac"))
            elif line.startswith("-"):
                cursor.setCharFormat(_make_format("#fca5a5"))
            elif line.startswith("@@"):
                cursor.setCharFormat(_make_format("#60a5fa"))
            else:
                cursor.setCharFormat(_make_format("#d1d5db"))
            cursor.insertText(line + "\n")

    def _set_view(self, mode: str) -> None:
        self._side_btn.setChecked(mode == "side")
        self._unified_btn.setChecked(mode == "unified")
        self._splitter.setVisible(mode == "side")
        self._unified_editor.setVisible(mode == "unified")

    def _copy_diff(self) -> None:
        """Copy the unified diff to clipboard."""
        from PySide6.QtWidgets import QApplication
        diff = self._unified_editor.toPlainText()
        if diff.strip():
            QApplication.clipboard().setText(diff)

    def clear(self) -> None:
        self._old_editor.clear()
        self._new_editor.clear()
        self._unified_editor.clear()
        self._file_label.setText("")
        self._stats_label.setText("")
