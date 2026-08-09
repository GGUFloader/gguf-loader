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
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from config import BUBBLE_FONT_SIZE, CHAT_BUBBLE_FONT_SIZE, FONT_FAMILY
from ui.agent_panel import AgentPanel
from widgets.chat_bubble import ChatBubble, _BubbleRow


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
        self.setObjectName("chatRoot")
        self.is_agent_mode = False
        self._is_dark = False
        self._font_size = CHAT_BUBBLE_FONT_SIZE
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

        # Empty-state hero (index 0) vs. live chat container (index 1).
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(48, 48, 48, 48)
        empty_layout.addStretch()
        hero = QLabel("\U0001F999")
        hero.setAlignment(Qt.AlignCenter)
        hero.setFont(QFont(FONT_FAMILY, 46))
        empty_layout.addWidget(hero)
        empty_title = QLabel("Welcome to GGUF Loader")
        empty_title.setObjectName("panelTitle")
        empty_title.setAlignment(Qt.AlignCenter)
        empty_title.setFont(QFont(FONT_FAMILY, 17, QFont.Bold))
        empty_layout.addWidget(empty_title)
        empty_hint = QLabel(
            "Load a GGUF model from the sidebar to start a conversation.\n"
            "Agent Mode adds tool use against a workspace folder."
        )
        empty_hint.setObjectName("mutedLabel")
        empty_hint.setAlignment(Qt.AlignCenter)
        empty_hint.setWordWrap(True)
        empty_layout.addWidget(empty_hint)
        empty_layout.addStretch()

        self.chat_stack = QStackedWidget()
        self.chat_stack.addWidget(self.empty_state)
        self.chat_stack.addWidget(self.chat_container)
        # Agent mode gets its own structured transcript page.
        self.agent_panel = AgentPanel()
        self.chat_stack.addWidget(self.agent_panel)
        self._agent_panel_visible = False
        self.chat_stack.setCurrentIndex(0)

        self.chat_scroll.setWidget(self.chat_stack)
        layout.addWidget(self.chat_scroll)

        # ---- input frame ----
        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
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
        self.agent_mode_btn.setObjectName("agentToggle")
        self.agent_mode_btn.setCheckable(True)
        self.agent_mode_btn.setMinimumHeight(35)
        self.agent_mode_btn.setMaximumWidth(160)
        self.agent_mode_btn.clicked.connect(self._on_agent_toggled)
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
        self.agent_status_label.setObjectName("agentStatus")
        self.agent_status_label.setVisible(False)
        controls.addWidget(self.agent_status_label)

        controls.addStretch()

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("primaryButton")
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
        label.setObjectName("systemMessage")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        font = QFont(FONT_FAMILY, 12)
        font.setItalic(True)
        label.setFont(font)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, label)
        self._maybe_hide_empty_state()
        self.scroll_to_bottom()

    def begin_streaming(self) -> None:
        """Start a new empty AI bubble that tokens will stream into."""
        self._current_ai_text = ""
        self._current_ai_bubble = ChatBubble("", is_user=False)
        self._apply_bubble_theme(self._current_ai_bubble)

        # Hide the empty pill until the first token arrives, so no empty
        # card flashes on slow first tokens.
        self._current_ai_bubble.setVisible(False)
        container = _BubbleRow(self._current_ai_bubble, is_user=False)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self._bubbles.append((container, self._current_ai_bubble))
        self._maybe_hide_empty_state()
        self.scroll_to_bottom()

    def stream_token(self, token: str) -> None:
        if self._current_ai_bubble is None:
            return
        self._current_ai_bubble.setVisible(True)
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
        if hasattr(self, "agent_panel"):
            self.agent_panel.clear()
        if not self._bubbles:
            self.empty_state.show()

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
        # Colors come from QSS via the state property.
        if "🟢" in text:
            state = "ok"
        elif "🟡" in text:
            state = "busy"
        elif "❌" in text:
            state = "err"
        else:
            state = ""
        self.agent_status_label.setProperty("state", state)
        self.agent_status_label.style().unpolish(self.agent_status_label)
        self.agent_status_label.style().polish(self.agent_status_label)

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
        """Remember the size so future bubbles use it, and restyle existing ones."""
        self._font_size = size
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
        self._maybe_hide_empty_state()

        container = _BubbleRow(bubble, is_user, is_rtl=bubble.is_rtl)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self._bubbles.append((container, bubble))
        self.scroll_to_bottom()

    def _apply_bubble_theme(self, bubble: ChatBubble) -> None:
        # set_font_size re-applies the style with the stored theme state,
        # then we push the panel's live theme so bubbles created while dark
        # mode is on start out correctly (not just after a toggle).
        bubble.set_font_size(self._font_size)
        bubble.update_style(self._is_dark)

    def set_agent_panel_visible(self, visible: bool) -> None:
        """Switch the display between the chat and the agent transcript."""
        self._agent_panel_visible = visible
        if visible:
            self.chat_stack.setCurrentIndex(2)
        else:
            self._maybe_hide_empty_state()

    def _maybe_hide_empty_state(self) -> None:
        """Swap between the empty-state hero and the live chat container."""
        if not hasattr(self, "chat_stack"):
            return
        if getattr(self, "_agent_panel_visible", False):
            return
        has_content = bool(self._bubbles) or self._current_ai_bubble is not None
        self.chat_stack.setCurrentIndex(1 if has_content else 0)

    def scroll_to_bottom(self) -> None:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))
