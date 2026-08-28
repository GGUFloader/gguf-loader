"""
ActivityLog - Compact chronological log of agent actions.

A lightweight alternative to TrajectoryInspector:
- Simple list of timestamped events
- Color-coded by type (tool, llm, error, user)
- Filterable by event type
- Exportable as text

Pattern from: Docker logs + GitHub Actions logs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


@dataclass
class LogEntry:
    timestamp: float
    event_type: str  # "tool", "llm", "user", "error", "status", "info"
    message: str
    detail: str = ""
    icon: str = ""


_ICONS = {
    "tool": "🔧",
    "llm": "🤖",
    "user": "👤",
    "error": "❌",
    "status": "📋",
    "info": "ℹ️",
}

_COLORS = {
    "tool": "#60a5fa",
    "llm": "#a78bfa",
    "user": "#34d399",
    "error": "#f87171",
    "status": "#fbbf24",
    "info": "#9ca3af",
}


class ActivityLog(QWidget):
    """Compact chronological activity log.

    Usage:
        log = ActivityLog()
        log.add_event("tool", "read_file: README.md")
        log.add_event("llm", "Generated response (256 tokens)")
    """

    event_added = Signal(str)  # event_type

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("activityLog")
        self._entries: list[LogEntry] = []
        self._filter: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        header.setSpacing(6)

        title = QLabel("📋 Activity Log")
        title.setObjectName("sectionEyebrow")
        title.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        header.addWidget(title)

        header.addStretch()

        self._count_label = QLabel("0 events")
        self._count_label.setStyleSheet("font-size: 9px; color: #6b7280;")
        header.addWidget(self._count_label)

        self._clear_btn = QPushButton("🗑")
        self._clear_btn.setFixedSize(20, 20)
        self._clear_btn.setStyleSheet("border: none; font-size: 10px;")
        self._clear_btn.setToolTip("Clear log")
        self._clear_btn.clicked.connect(self.clear)
        header.addWidget(self._clear_btn)

        layout.addLayout(header)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter events...")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.setMaximumHeight(22)
        self._filter_input.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        self._filter_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_input)

        # Type filter buttons
        self._type_buttons: dict[str, QPushButton] = {}
        for event_type in ["tool", "llm", "user", "error", "status", "info"]:
            btn = QPushButton(_ICONS.get(event_type, ""))
            btn.setFixedSize(22, 22)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setToolTip(f"Show {event_type} events")
            btn.setStyleSheet("font-size: 10px; border: none; padding: 0;")
            btn.clicked.connect(lambda _c, t=event_type: self._toggle_type(t))
            self._type_buttons[event_type] = btn
            filter_row.addWidget(btn)

        layout.addLayout(filter_row)

        # Log display
        self._log_display = QTextEdit()
        self._log_display.setReadOnly(True)
        self._log_display.setFont(QFont("Consolas", 9))
        self._log_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._log_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._log_display.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._log_display, 1)

        # Active type filters
        self._active_types: set[str] = set(_ICONS.keys())

    def add_event(self, event_type: str, message: str, detail: str = "") -> None:
        """Add an event to the log."""
        entry = LogEntry(
            timestamp=time.monotonic(),
            event_type=event_type,
            message=message,
            detail=detail,
            icon=_ICONS.get(event_type, "ℹ️"),
        )
        self._entries.append(entry)
        self._render_entry(entry)
        self._count_label.setText(f"{len(self._entries)} events")
        self.event_added.emit(event_type)

    def add_tool_call(self, tool: str, params: dict, result: dict | None = None) -> None:
        """Convenience: add a tool call event."""
        status = "✅" if result and result.get("status") == "success" else "⏳"
        path = params.get("path", "")
        msg = f"{status} {tool}" + (f" → {path}" if path else "")
        self.add_event("tool", msg)

    def add_llm_call(self, tokens: int = 0, duration_ms: int = 0) -> None:
        """Convenience: add an LLM call event."""
        parts = ["🤖 LLM call"]
        if tokens:
            parts.append(f"{tokens} tokens")
        if duration_ms:
            parts.append(f"{duration_ms}ms")
        self.add_event("llm", " ".join(parts))

    def add_user_message(self, text: str) -> None:
        """Convenience: add a user message event."""
        preview = text[:80] + ("…" if len(text) > 80 else "")
        self.add_event("user", preview)

    def add_error(self, message: str) -> None:
        """Convenience: add an error event."""
        self.add_event("error", message)

    def clear(self) -> None:
        """Clear all log entries."""
        self._entries.clear()
        self._log_display.clear()
        self._count_label.setText("0 events")

    def _render_entry(self, entry: LogEntry) -> None:
        """Append a single entry to the log display."""
        if entry.event_type not in self._active_types:
            return
        if self._filter and self._filter.lower() not in entry.message.lower():
            return

        cursor = QTextCursor(self._log_display.document())
        cursor.movePosition(QTextCursor.End)

        # Timestamp
        elapsed = entry.timestamp - (self._entries[0].timestamp if self._entries else entry.timestamp)
        fmt = QTextCharFormat()
        fmt.setForeground(_COLORS.get(entry.event_type, "#9ca3af"))
        cursor.setCharFormat(fmt)
        cursor.insertText(f"{elapsed:6.1f}s ")

        # Icon + message
        cursor.insertText(f"{entry.icon} {entry.message}\n")

        # Detail (indented)
        if entry.detail:
            fmt2 = QTextCharFormat()
            fmt2.setForeground(_COLORS.get("info", "#6b7280"))
            cursor.setCharFormat(fmt2)
            detail_preview = entry.detail[:200] + ("…" if len(entry.detail) > 200 else "")
            for line in detail_preview.split("\n"):
                cursor.insertText(f"       {line}\n")

        # Auto-scroll
        sb = self._log_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _apply_filter(self, text: str) -> None:
        self._filter = text
        self._refresh_display()

    def _toggle_type(self, event_type: str) -> None:
        if event_type in self._active_types:
            self._active_types.discard(event_type)
            self._type_buttons[event_type].setChecked(False)
        else:
            self._active_types.add(event_type)
            self._type_buttons[event_type].setChecked(True)
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Re-render all entries with current filters."""
        self._log_display.clear()
        for entry in self._entries:
            self._render_entry(entry)

    def export_text(self) -> str:
        """Export the log as plain text."""
        lines = []
        for entry in self._entries:
            elapsed = entry.timestamp - (self._entries[0].timestamp if self._entries else entry.timestamp)
            lines.append(f"[{elapsed:.1f}s] {entry.icon} {entry.message}")
            if entry.detail:
                for line in entry.detail.split("\n"):
                    lines.append(f"       {line}")
        return "\n".join(lines)
