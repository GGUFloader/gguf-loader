"""
ToolCard - Enhanced tool call card with diff display and risk badges.

Inspired by:
- Aider's side-by-side diffs (cmd_diff with Rich syntax highlighting)
- OpenHands' action cards with SecurityRisk badges
- DeepSeek's GenericCommandCard with running/ok/error states
"""

from __future__ import annotations

import difflib
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QTextEdit, QVBoxLayout,
)


def _theme_pair():
    from ggufloader.ui.theme import DARK_TOKENS, LIGHT_TOKENS
    return DARK_TOKENS, LIGHT_TOKENS


# Risk level colors (OpenHands SecurityRisk pattern)
RISK_COLORS = {
    "low": "#22c55e",      # green
    "medium": "#f59e0b",   # amber
    "high": "#ef4444",     # red
}

RISK_LABELS = {
    "low": "🟢 Low Risk",
    "medium": "🟡 Medium Risk",
    "high": "🔴 High Risk",
}


class DiffView(QTextEdit):
    """Read-only text edit showing a unified diff with syntax coloring."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(60)
        self.setMaximumHeight(300)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

    def set_diff(self, old_text: str, new_text: str) -> None:
        """Display a unified diff between old and new text."""
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile="before", tofile="after",
            lineterm="",
        ))
        if not diff:
            self.setPlainText("(no changes)")
            return

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        for line in diff:
            if line.startswith("+++") or line.startswith("---"):
                fmt = self._make_format("#94a3b8")  # muted
            elif line.startswith("@@"):
                fmt = self._make_format("#6366f1")  # accent
            elif line.startswith("+"):
                fmt = self._make_format("#22c55e", bg="#052e16")  # green on dark green
            elif line.startswith("-"):
                fmt = self._make_format("#ef4444", bg="#450a0a")  # red on dark red
            else:
                fmt = self._make_format("#e2e8f0")  # normal text

            cursor.insertText(line.rstrip("\n") + "\n", fmt)

        # Auto-size
        doc = self.document()
        doc.setTextWidth(self.viewport().width())
        height = int(doc.size().height()) + 10
        self.setFixedHeight(min(max(height, 60), 300))

    def _make_format(self, fg: str, bg: str = None) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(fg))
        if bg:
            fmt.setBackground(QColor(bg))
        return fmt


class ToolCard(QFrame):
    """Enhanced tool call card with status, risk badge, and optional diff.

    Features:
    - Running/ok/error state indicator (DeepSeek GenericCommandCard)
    - Risk badge on high-risk actions (OpenHands SecurityRisk)
    - Expandable diff view for file edits (Aider side-by-side)
    """

    def __init__(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        risk: str = "low",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.tool_name = tool_name
        self.params = params
        self.result = result
        self.risk = risk
        self._expanded = False
        self._diff_view: Optional[DiffView] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Header row: status dot + tool name + risk badge
        header = QHBoxLayout()
        header.setSpacing(6)

        # Status dot (DeepSeek StateDot pattern)
        self._status_dot = QLabel("●")
        self._status_dot.setFixedWidth(12)
        self._update_status_dot()
        header.addWidget(self._status_dot)

        # Tool name
        name_label = QLabel(self.tool_name)
        name_label.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        header.addWidget(name_label)

        # Summary
        summary = self._make_summary()
        if summary:
            summary_label = QLabel(summary)
            summary_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
            header.addWidget(summary_label)

        header.addStretch()

        # Risk badge (OpenHands SecurityRisk pattern)
        if self.risk in RISK_COLORS:
            risk_label = QLabel(RISK_LABELS.get(self.risk, self.risk))
            risk_label.setStyleSheet(
                f"color: {RISK_COLORS[self.risk]}; font-size: 10px; "
                f"padding: 2px 6px; border-radius: 4px; "
                f"background: {RISK_COLORS[self.risk]}22;"
            )
            header.addWidget(risk_label)

        layout.addLayout(header)

        # Diff view (expandable for write_file/edit_file)
        if self.tool_name in ("write_file", "edit_file") and self.result:
            old_content = self.params.get("old_content", "")
            new_content = self.params.get("content", "")
            if old_content or new_content:
                self._diff_view = DiffView()
                self._diff_view.setVisible(False)
                layout.addWidget(self._diff_view)

        # Error display
        if self.result and self.result.get("status") == "error":
            error = self.result.get("error", "Unknown error")
            error_label = QLabel(f"✗ {error}")
            error_label.setStyleSheet("color: #ef4444; font-size: 11px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

    def _update_status_dot(self) -> None:
        """Update the status dot color based on state."""
        if self.result is None:
            color = "#6366f1"  # blue = running
        elif self.result.get("status") == "success":
            color = "#22c55e"  # green = ok
        else:
            color = "#ef4444"  # red = error
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _make_summary(self) -> str:
        """Make a one-line summary of the tool call."""
        if self.tool_name == "write_file":
            return f"Write {self.params.get('path', 'file')}"
        if self.tool_name == "edit_file":
            return f"Edit {self.params.get('path', 'file')}"
        if self.tool_name == "read_file":
            return f"Read {self.params.get('path', 'file')}"
        if self.tool_name == "list_directory":
            return f"List {self.params.get('path', '.')}"
        if self.tool_name == "search_files":
            return f"Search '{self.params.get('pattern', '')}'"
        if self.tool_name == "run_command":
            cmd = self.params.get("command", "")
            return f"Run: {cmd[:40]}{'...' if len(cmd) > 40 else ''}"
        return ""

    def set_result(self, result: Dict[str, Any]) -> None:
        """Update the card with execution results."""
        self.result = result
        self._update_status_dot()

    def toggle_diff(self) -> None:
        """Toggle the diff view visibility."""
        if self._diff_view is not None:
            self._expanded = not self._expanded
            self._diff_view.setVisible(self._expanded)
