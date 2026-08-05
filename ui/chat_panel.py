"""
ChatPanel - Chat display, input area and agent-mode controls.

The panel is deliberately dumb: it renders messages and emits signals;
all logic (model state, generation, agent lifecycle) lives in
MainWindow.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from config import BUBBLE_FONT_SIZE, FONT_FAMILY
from widgets.chat_bubble import ChatBubble


class MessageInput(QTextEdit):
    """Input box where plain Enter sends and Shift+Enter inserts a newline."""

    send_requested = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
                return
        else:
            super().keyPressEvent(event)


class ChatPanel(QWidget):
    """Message list + input row with agent-mode controls."""

    message_submitted = Signal(str)
    agent_mode_toggled = Signal(bool)
    workspace_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.is_agent_mode = False
        self._is_dark = False
        self._current_ai_bubble: ChatBubble | None = None
        self._current_ai_text = ""
        self._bubbles: list[tuple[QWidget, ChatBubble]] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ---- scrollable message area ----
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(10)
        self.chat_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll)

        # ---- input frame ----
        input_frame = QFrame()
        input_frame.setFrameStyle(QFrame.StyledPanel)
        input_frame.setMaximumHeight(200)

        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(15, 10, 15, 10)

        self.input_text = MessageInput()
        self.input_text.setPlaceholderText("Type your message here...")
        self.input_text.setMaximumHeight(80)
        self.input_text.setFont(QFont(FONT_FAMILY, BUBBLE_FONT_SIZE))
        self.input_text.textChanged.connect(self._on_input_changed)
        self.input_text.send_requested.connect(self._submit)
        input_layout.addWidget(self.input_text)

        # Agent controls row
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.agent_mode_btn = QPushButton("🤖 Agent Mode: OFF")
        self.agent_mode_btn.setCheckable(True)
        self.agent_mode_btn.setMinimumHeight(35)
        self.agent_mode_btn.setMaximumWidth(150)
        self.agent_mode_btn.clicked.connect(self._on_agent_toggled)
        self.agent_mode_btn.setStyleSheet("""
            QPushButton { background-color: #6c757d; color: white; border: none;
                          border-radius: 6px; padding: 8px 12px; font-size: 11px;
                          font-weight: bold; }
            QPushButton:hover { background-color: #5a6268; }
            QPushButton:checked { background-color: #28a745; }
            QPushButton:checked:hover { background-color: #218838; }
        """)
        controls.addWidget(self.agent_mode_btn)

        self.workspace_label = QLabel("📁")
        self.workspace_label.setToolTip("Workspace folder")
        self.workspace_label.setVisible(False)
        controls.addWidget(self.workspace_label)

        self.workspace_combo = QComboBox()
        self.workspace_combo.setEditable(True)
        self.workspace_combo.setPlaceholderText("Select workspace...")
        self.workspace_combo.setMinimumHeight(35)
        self.workspace_combo.setMinimumWidth(200)
        self.workspace_combo.addItems(["./agent_workspace", "./workspace", "./projects"])
        self.workspace_combo.setCurrentText("./agent_workspace")
        self.workspace_combo.setVisible(False)
        self.workspace_combo.editTextChanged.connect(self.workspace_selected.emit)
        controls.addWidget(self.workspace_combo)

        self.workspace_browse_btn = QPushButton("📁")
        self.workspace_browse_btn.setMaximumWidth(35)
        self.workspace_browse_btn.setMinimumHeight(35)
        self.workspace_browse_btn.setToolTip("Browse for workspace folder")
        self.workspace_browse_btn.setVisible(False)
        controls.addWidget(self.workspace_browse_btn)

        self.agent_status_label = QLabel("⚪ Ready")
        self.agent_status_label.setStyleSheet("color: #666; font-size: 10px;")
        self.agent_status_label.setVisible(False)
        controls.addWidget(self.agent_status_label)

        controls.addStretch()

        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumSize(100, 35)
        self.send_btn.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._submit)
        controls.addWidget(self.send_btn)

        input_layout.addLayout(controls)
        layout.addWidget(input_frame)

    # ------------------------------------------------------------------
    # Message rendering
    # ------------------------------------------------------------------
    def add_user_message(self, text: str) -> None:
        self._add_bubble(text, is_user=True)

    def add_ai_message(self, text: str) -> None:
        self._add_bubble(text, is_user=False)

    def add_system_message(self, text: str) -> None:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        font = QFont(FONT_FAMILY, 12)
        font.setItalic(True)
        label.setFont(font)
        label.setStyleSheet("color: #888; margin: 10px; padding: 10px;")
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, label)
        self.scroll_to_bottom()

    def begin_streaming(self) -> None:
        """Start a new empty AI bubble that tokens will stream into."""
        self._current_ai_text = ""
        self._current_ai_bubble = ChatBubble("", is_user=False)
        self._apply_bubble_theme(self._current_ai_bubble)

        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._current_ai_bubble, 3)
        row.addStretch(1)

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self._bubbles.append((container, self._current_ai_bubble))
        self.scroll_to_bottom()

    def stream_token(self, token: str) -> None:
        if self._current_ai_bubble is None:
            return
        self._current_ai_text += token
        self._current_ai_bubble.update_text(self._current_ai_text)
        self.scroll_to_bottom()

    def finish_streaming(self) -> str:
        """Finalize the streaming bubble; returns the accumulated text."""
        text = self._current_ai_text.strip()
        self._current_ai_bubble = None
        self._current_ai_text = ""
        return text

    def clear_chat(self) -> None:
        for container, _bubble in self._bubbles:
            container.setParent(None)
        self._bubbles.clear()
        self._current_ai_bubble = None
        self._current_ai_text = ""

    # ------------------------------------------------------------------
    # Agent mode controls
    # ------------------------------------------------------------------
    def show_agent_controls(self, visible: bool) -> None:
        self.workspace_label.setVisible(visible)
        self.workspace_combo.setVisible(visible)
        self.workspace_browse_btn.setVisible(visible)
        self.agent_status_label.setVisible(visible)

    def set_agent_status(self, text: str) -> None:
        self.agent_status_label.setText(text)
        if "🟢" in text:
            color = "#28a745"
        elif "🟡" in text:
            color = "#ffc107"
        elif "❌" in text:
            color = "#dc3545"
        else:
            color = "#666"
        self.agent_status_label.setStyleSheet(f"color: {color}; font-size: 10px;")

    def get_workspace(self) -> str:
        return self.workspace_combo.currentText().strip()

    def set_workspace(self, path: str) -> None:
        self.workspace_combo.setCurrentText(path)

    # ------------------------------------------------------------------
    # Input state
    # ------------------------------------------------------------------
    def set_send_enabled(self, enabled: bool) -> None:
        self.send_btn.setEnabled(enabled)

    def set_input_enabled(self, enabled: bool) -> None:
        self.input_text.setEnabled(enabled)

    def set_placeholder(self, text: str) -> None:
        self.input_text.setPlaceholderText(text)

    def apply_font_size(self, size: int) -> None:
        for _container, bubble in self._bubbles:
            bubble.set_font_size(size)

    def apply_theme(self, is_dark: bool) -> None:
        self._is_dark = is_dark
        for _container, bubble in self._bubbles:
            bubble.update_style(is_dark)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _submit(self) -> None:
        text = self.input_text.toPlainText().strip()
        if not text:
            return
        self.input_text.clear()
        self.message_submitted.emit(text)

    def _on_input_changed(self) -> None:
        has_text = bool(self.input_text.toPlainText().strip())
        self.send_btn.setEnabled(has_text)

    def _on_agent_toggled(self, checked: bool) -> None:
        self.is_agent_mode = checked
        self.agent_mode_btn.setText("🤖 Agent Mode: ON" if checked else "🤖 Agent Mode: OFF")
        self.agent_mode_toggled.emit(checked)

    def _add_bubble(self, text: str, is_user: bool) -> None:
        bubble = ChatBubble(text, is_user)
        self._apply_bubble_theme(bubble)

        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        if is_user:
            row.addStretch(1)
            row.addWidget(bubble, 3)
        else:
            row.addWidget(bubble, 3)
            row.addStretch(1)

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self._bubbles.append((container, bubble))
        self.scroll_to_bottom()

    def _apply_bubble_theme(self, bubble: ChatBubble) -> None:
        bubble.update_style(self._is_dark)

    def scroll_to_bottom(self) -> None:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))
