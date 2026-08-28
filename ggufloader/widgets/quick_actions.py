"""
QuickActions - One-click toolbar for common agent operations.

Pattern from: VS Code command palette + Aider's slash commands.
A horizontal toolbar of icon buttons for frequently used actions:
- New chat, clear chat, export
- Run tests, commit changes
- Toggle agent mode, workspace browser
- Undo, redo, stop
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class QuickActionButton(QPushButton):
    """A small icon button for the quick actions bar."""

    def __init__(self, icon: str, tooltip: str, parent=None):
        super().__init__(icon, parent)
        self.setToolTip(tooltip)
        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton { border: none; border-radius: 6px; font-size: 16px; }"
            "QPushButton:hover { background: #374151; }"
            "QPushButton:pressed { background: #4b5563; }"
        )


class QuickActions(QWidget):
    """Quick actions toolbar for the agent interface.

    Usage:
        toolbar = QuickActions()
        toolbar.on_action.connect(handle_action)
    """

    on_action = Signal(str)  # action_id

    # Action definitions: (id, icon, tooltip)
    ACTIONS = [
        ("new_chat", "💬", "New chat session"),
        ("clear", "🗑️", "Clear chat"),
        ("undo", "↩️", "Undo last change"),
        ("stop", "⏹", "Stop generation"),
        ("sep1", "", ""),
        ("mode", "🤖", "Toggle agent mode"),
        ("preset", "🎯", "Select agent preset"),
        ("workspace", "📁", "Select workspace"),
        ("sep2", "", ""),
        ("run_tests", "🧪", "Run tests"),
        ("commit", "📦", "Commit changes"),
        ("diff", "📊", "Show diff"),
        ("sep3", "", ""),
        ("export", "📤", "Export conversation"),
        ("replay", "🔄", "Replay session"),
        ("health", "💓", "System health"),
        ("features", "⚙️", "Feature dashboard"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("quickActions")
        self.setFixedHeight(38)
        self._buttons: dict[str, QuickActionButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(2)

        for action_id, icon, tooltip in self.ACTIONS:
            if action_id.startswith("sep"):
                layout.addSpacerItem(QSpacerItem(8, 0))
                continue

            btn = QuickActionButton(icon, tooltip)
            btn.clicked.connect(lambda _c, aid=action_id: self.on_action.emit(aid))
            self._buttons[action_id] = btn
            layout.addWidget(btn)

        layout.addStretch()

    def set_enabled(self, action_id: str, enabled: bool) -> None:
        """Enable or disable a specific action button."""
        btn = self._buttons.get(action_id)
        if btn:
            btn.setEnabled(enabled)

    def set_running(self, running: bool) -> None:
        """Update button states based on running status."""
        self._buttons["stop"].setVisible(running)
        self._buttons["new_chat"].setEnabled(not running)
        self._buttons["clear"].setEnabled(not running)
        self._buttons["commit"].setEnabled(not running)
        self._buttons["run_tests"].setEnabled(not running)
