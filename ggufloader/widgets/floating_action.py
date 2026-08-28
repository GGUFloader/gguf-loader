"""
FloatingAction - Circular floating action button for agent mode.

Expands on click to show context-aware quick actions:
- Stop generation
- New chat
- Toggle agent mode
- Open settings

Pattern from: Material Design FAB + Android quick settings.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class FloatingAction(QWidget):
    """Floating action button that expands to show quick actions.

    Usage:
        fab = FloatingAction()
        fab.action_clicked.connect(handle_action)
        parent_layout.addWidget(fab)
    """

    action_clicked = Signal(str)  # action_id

    ACTIONS = [
        ("stop", "⏹", "Stop generation"),
        ("new_chat", "💬", "New chat"),
        ("agent", "🤖", "Toggle agent mode"),
        ("settings", "⚙️", "Agent settings"),
        ("search", "🔍", "Search chat"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("floatingAction")
        self._expanded = False
        self._build_ui()

    def _build_ui(self) -> None:
        self.setFixedSize(56, 56)

        # Main FAB button
        self._main_btn = QPushButton("🤖")
        self._main_btn.setFixedSize(56, 56)
        self._main_btn.setFont(QFont(FONT_FAMILY, 20))
        self._main_btn.setCursor(Qt.PointingHandCursor)
        self._main_btn.setToolTip("Quick Actions")
        self._main_btn.setStyleSheet("""
            QPushButton {
                background: #e8a33d;
                color: #191204;
                border: none;
                border-radius: 28px;
                font-size: 20px;
            }
            QPushButton:hover {
                background: #f0b458;
            }
            QPushButton:pressed {
                background: #cc8a27;
            }
        """)
        self._main_btn.clicked.connect(self._toggle_expand)

        # Action buttons container (hidden by default)
        self._actions_widget = QWidget()
        self._actions_widget.setVisible(False)
        actions_layout = QVBoxLayout(self._actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)

        self._action_buttons: dict[str, QPushButton] = {}
        for action_id, icon, tooltip in self.ACTIONS:
            btn = QPushButton(icon)
            btn.setFixedSize(40, 40)
            btn.setFont(QFont(FONT_FAMILY, 14))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: #374151;
                    color: #e5e7eb;
                    border: none;
                    border-radius: 20px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #4b5563;
                }
            """)
            btn.clicked.connect(lambda _c, aid=action_id: self._on_action(aid))
            self._action_buttons[action_id] = btn
            actions_layout.addWidget(btn)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._actions_widget, 0, Qt.AlignRight)
        layout.addWidget(self._main_btn, 0, Qt.AlignRight)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self._actions_widget.setVisible(self._expanded)
        self._main_btn.setText("✕" if self._expanded else "🤖")

    def _on_action(self, action_id: str) -> None:
        self.action_clicked.emit(action_id)
        # Collapse after action
        if self._expanded:
            self._toggle_expand()

    def set_visible_action(self, action_id: str, visible: bool) -> None:
        """Show/hide a specific action button."""
        btn = self._action_buttons.get(action_id)
        if btn:
            btn.setVisible(visible)

    def update_for_state(self, is_generating: bool, is_agent: bool) -> None:
        """Update button states based on current app state."""
        self._action_buttons["stop"].setVisible(is_generating)
        self._action_buttons["agent"].setText("🤖" if not is_agent else "💬")
