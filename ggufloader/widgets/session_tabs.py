"""
SessionTabs - Horizontal tab bar for switching between concurrent sessions.

Pattern from: DeepSeek Harness TurnNavigator + browser tab paradigm.
Each tab shows session title, close button, and activity indicator.
Tabs are reorderable and support middle-click close.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class SessionTabButton(QPushButton):
    """A single session tab with title, close button, and activity dot."""

    clicked_tab = Signal(str)  # session_id
    close_clicked = Signal(str)  # session_id

    def __init__(self, session_id: str, title: str, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self._is_active = False
        self._is_generating = False
        self.setObjectName("sessionTab")
        self._build_ui(title)

    def _build_ui(self, title: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)

        # Activity dot (green = active, yellow = generating)
        self._dot = QLabel("●")
        self._dot.setFixedWidth(10)
        self._dot.setAlignment(Qt.AlignCenter)
        self._update_dot_color()
        layout.addWidget(self._dot)

        # Title
        self._title_label = QLabel(title or "New Chat")
        self._title_label.setObjectName("sessionTabTitle")
        font = QFont(FONT_FAMILY, 11)
        self._title_label.setFont(font)
        self._title_label.setMaximumWidth(120)
        layout.addWidget(self._title_label)

        # Close button
        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("sessionTabClose")
        self._close_btn.setFixedSize(18, 18)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(lambda: self.close_clicked.emit(self.session_id))
        layout.addWidget(self._close_btn)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self.setMinimumWidth(80)
        self.setMaximumWidth(200)

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self._update_dot_color()

    def set_generating(self, generating: bool) -> None:
        self._is_generating = generating
        self._update_dot_color()

    def update_title(self, title: str) -> None:
        self._title_label.setText(title or "New Chat")

    def _update_dot_color(self) -> None:
        if self._is_generating:
            self._dot.setText("●")
            self._dot.setStyleSheet("color: #f59e0b; font-size: 8px;")  # yellow
        elif self._is_active:
            self._dot.setText("●")
            self._dot.setStyleSheet("color: #22c55e; font-size: 8px;")  # green
        else:
            self._dot.setText("●")
            self._dot.setStyleSheet("color: #6b7280; font-size: 8px;")  # gray


class SessionTabs(QWidget):
    """Horizontal scrollable tab bar for multi-session switching.

    Features:
    - Each tab shows title, activity indicator, close button
    - New session button (+)
    - Scroll when tabs overflow
    """

    session_switched = Signal(str)  # session_id
    session_closed = Signal(str)  # session_id
    new_session_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sessionTabs")
        self._tabs: dict[str, SessionTabButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable tab area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("sessionTabsScroll")
        scroll.setFixedHeight(36)

        self._tab_container = QWidget()
        self._tab_layout = QHBoxLayout(self._tab_container)
        self._tab_layout.setContentsMargins(4, 2, 4, 2)
        self._tab_layout.setSpacing(2)
        self._tab_layout.addStretch()
        scroll.setWidget(self._tab_container)
        layout.addWidget(scroll, 1)

        # New session button
        new_btn = QPushButton("+")
        new_btn.setObjectName("sessionTabNew")
        new_btn.setFixedSize(28, 28)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setToolTip("New chat session")
        new_btn.clicked.connect(self.new_session_requested.emit)
        layout.addWidget(new_btn)

    def add_tab(self, session_id: str, title: str = "New Chat") -> None:
        if session_id in self._tabs:
            return
        tab = SessionTabButton(session_id, title)
        tab.clicked_tab.connect(self.session_switched.emit)
        tab.close_clicked.connect(self.session_closed.emit)
        self._tabs[session_id] = tab
        self._tab_layout.insertWidget(self._tab_layout.count() - 1, tab)

    def remove_tab(self, session_id: str) -> None:
        tab = self._tabs.pop(session_id, None)
        if tab is not None:
            tab.setParent(None)

    def set_active_tab(self, session_id: str) -> None:
        for sid, tab in self._tabs.items():
            tab.set_active(sid == session_id)

    def update_tab_title(self, session_id: str, title: str) -> None:
        tab = self._tabs.get(session_id)
        if tab is not None:
            tab.update_title(title)

    def set_tab_generating(self, session_id: str, generating: bool) -> None:
        tab = self._tabs.get(session_id)
        if tab is not None:
            tab.set_generating(generating)

    def clear_all(self) -> None:
        for tab in self._tabs.values():
            tab.setParent(None)
        self._tabs.clear()
