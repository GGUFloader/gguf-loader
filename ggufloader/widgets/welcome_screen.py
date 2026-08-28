"""
WelcomeScreen - Rich welcome screen shown when no chat is active.

Shows:
- App branding
- Recent sessions list
- Quick start buttons (new chat, load model, agent mode)
- Tips and keyboard shortcuts
- Model status

Pattern from: ChatGPT home screen + Claude welcome page.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class WelcomeScreen(QWidget):
    """Rich welcome screen for the empty state.

    Usage:
        welcome = WelcomeScreen()
        welcome.new_chat_requested.connect(start_new_chat)
        welcome.load_model_requested.connect(open_model_dialog)
        welcome.session_selected.connect(load_session)
    """

    new_chat_requested = Signal()
    load_model_requested = Signal()
    agent_mode_requested = Signal()
    session_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcomeScreen")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setSpacing(24)

        # Brand
        icon = QLabel("🦜")
        icon.setFont(QFont(FONT_FAMILY, 56))
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("GGUF Loader")
        title.setFont(QFont(FONT_FAMILY, 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Local LLM runtime for GGUF models")
        subtitle.setObjectName("mutedLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # Quick start buttons
        quick_frame = QFrame()
        quick_frame.setObjectName("toolCard")
        quick_layout = QHBoxLayout(quick_frame)
        quick_layout.setContentsMargins(16, 12, 16, 12)
        quick_layout.setSpacing(12)

        quick_layout.addWidget(self._make_quick_btn(
            "💬", "New Chat", "Start a new conversation",
            self.new_chat_requested.emit))
        quick_layout.addWidget(self._make_quick_btn(
            "📦", "Load Model", "Load a GGUF model file",
            self.load_model_requested.emit))
        quick_layout.addWidget(self._make_quick_btn(
            "🤖", "Agent Mode", "Toggle agent with tools",
            self.agent_mode_requested.emit))

        layout.addWidget(quick_frame)

        # Tips section
        tips_label = QLabel("💡 TIPS")
        tips_label.setObjectName("sectionEyebrow")
        tips_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        tips_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(tips_label)

        tips_grid = QGridLayout()
        tips_grid.setSpacing(8)

        tips = [
            ("⌨️", "Ctrl+M", "Toggle agent mode"),
            ("📂", "Ctrl+O", "Load a model"),
            ("🔍", "Ctrl+F", "Search in chat"),
            ("⚙️", "Ctrl+,", "Agent settings"),
            ("📋", "Ctrl+/", "Keyboard shortcuts"),
            ("🆕", "Ctrl+N", "New chat session"),
        ]
        for i, (icon, key, desc) in enumerate(tips):
            row, col = divmod(i, 3)
            tip = self._make_tip(icon, key, desc)
            tips_grid.addWidget(tip, row, col)

        layout.addLayout(tips_grid)

        # Recent sessions (placeholder - populated externally)
        self._recent_label = QLabel("📜 RECENT SESSIONS")
        self._recent_label.setObjectName("sectionEyebrow")
        self._recent_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        self._recent_label.setAlignment(Qt.AlignCenter)
        self._recent_label.setVisible(False)
        layout.addWidget(self._recent_label)

        self._recent_container = QWidget()
        self._recent_layout = QVBoxLayout(self._recent_container)
        self._recent_layout.setSpacing(4)
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._recent_container)

        layout.addStretch()

        # Footer
        footer = QLabel("Built by Hussain Nazary · @hussainnazary2")
        footer.setObjectName("mutedLabel")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("font-size: 9px; color: #4b5563;")
        layout.addWidget(footer)

    def _make_quick_btn(self, icon: str, title: str, desc: str, callback) -> QPushButton:
        btn = QPushButton(f"{icon}\n{title}")
        btn.setMinimumSize(120, 60)
        btn.setToolTip(desc)
        btn.setObjectName("gpuInstallBtn")
        btn.setStyleSheet(
            "QPushButton { font-size: 12px; padding: 8px; border-radius: 8px; }"
        )
        btn.clicked.connect(callback)
        return btn

    def _make_tip(self, icon: str, key: str, desc: str) -> QFrame:
        frame = QFrame()
        row = QHBoxLayout(frame)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(6)

        icon_label = QLabel(icon)
        icon_label.setFont(QFont(FONT_FAMILY, 12))
        row.addWidget(icon_label)

        key_label = QLabel(key)
        key_label.setFont(QFont("Consolas", 9))
        key_label.setStyleSheet("background: #374151; padding: 2px 6px; border-radius: 3px;")
        row.addWidget(key_label)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet("font-size: 10px; color: #9ca3af;")
        row.addWidget(desc_label)

        return frame

    def add_recent_session(self, session_id: str, title: str) -> None:
        """Add a recent session to the list."""
        self._recent_label.setVisible(True)

        btn = QPushButton(f"💬 {title}")
        btn.setObjectName("gpuInstallBtn")
        btn.setMinimumHeight(32)
        btn.setStyleSheet(
            "QPushButton { text-align: left; padding: 6px 12px; font-size: 11px; }"
        )
        btn.clicked.connect(lambda: self.session_selected.emit(session_id))
        self._recent_layout.addWidget(btn)

    def clear_recent(self) -> None:
        """Clear the recent sessions list."""
        while self._recent_layout.count():
            item = self._recent_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._recent_label.setVisible(False)
