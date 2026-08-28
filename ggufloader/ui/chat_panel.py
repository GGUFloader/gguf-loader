"""
ChatPanel - Chat display, input area and agent-mode controls.

The panel is deliberately dumb: it renders messages and emits signals;
all logic (model state, generation, agent lifecycle) lives in
MainWindow.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from ggufloader.config import BUBBLE_FONT_SIZE, CHAT_BUBBLE_FONT_SIZE, FONT_FAMILY
from ggufloader.core.reasoning import ReasoningStreamParser, format_answer, split_reasoning
from ggufloader.ui.agent_panel import AgentPanel
from ggufloader.ui.slash_commands import SlashCommands
from ggufloader.widgets.chat_bubble import ChatBubble, _BubbleRow
from ggufloader.widgets.reasoning_block import ReasoningBlock


class MessageInput(QTextEdit):
    """Input box where plain Enter sends and Shift+Enter inserts a newline.

    Supports drag-and-drop of text files (.txt, .md, .py, .json, etc.).
    """

    send_requested = Signal()
    stop_requested = Signal()  # Esc pressed while generating
    file_dropped = Signal(str, str)  # (filename, content)

    # Supported text file extensions
    _TEXT_EXTS = frozenset({
        ".txt", ".md", ".rst", ".py", ".js", ".ts", ".jsx", ".tsx",
        ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".conf",
        ".html", ".css", ".xml", ".csv", ".log", ".sh", ".bat",
        ".rs", ".go", ".java", ".c", ".cpp", ".h", ".hpp",
        ".rb", ".php", ".sql", ".r", ".m", ".swift",
    })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if not urls:
            super().dropEvent(event)
            return
        for url in urls:
            path = url.toLocalFile()
            if not path:
                continue
            import os
            ext = os.path.splitext(path)[1].lower()
            if ext not in self._TEXT_EXTS:
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(10000)  # limit to 10k chars
                filename = os.path.basename(path)
                self.file_dropped.emit(filename, content)
            except Exception:
                pass
        event.acceptProposedAction()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
                return
        elif event.key() == Qt.Key_Escape:
            self.stop_requested.emit()
            return
        else:
            super().keyPressEvent(event)


class ChatPanel(QWidget):
    """Message list + input row with agent-mode controls."""

    message_submitted = Signal(str)
    agent_mode_toggled = Signal(bool)
    workspace_selected = Signal(str)
    stop_requested = Signal()
    regenerate_requested = Signal()
    edit_last_requested = Signal(str)
    delete_message_requested = Signal(str)  # content of message to delete
    feedback_requested = Signal(str, str)  # status ("up"/"down"), message text
    attach_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatRoot")
        self.is_agent_mode = False
        self._is_dark = False
        self._font_size = CHAT_BUBBLE_FONT_SIZE
        self._current_ai_bubble: ChatBubble | None = None
        self._current_ai_text = ""
        self._bubbles: list[tuple[QWidget, ChatBubble]] = []
        self._generating = False
        self._followup_widget: QWidget | None = None
        self._parser: ReasoningStreamParser | None = None
        self._reasoning: ReasoningBlock | None = None
        self._reasoning_blocks: list[ReasoningBlock] = []
        # Slash commands (Aider pattern)
        self._slash_commands = SlashCommands()
        # Smart autocomplete (Aider AutoCompleter pattern)
        self._autocomplete = None  # lazy init after build_ui
        # TTFT tracking (DeepSeek StatsLine pattern)
        self._ttft_start: float | None = None
        self._last_ttft_ms: int | None = None
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

        # ---- search bar (hidden by default, Ctrl+F to toggle) ----
        self._search_bar = QWidget()
        self._search_bar.setObjectName("searchBar")
        self._search_bar.setVisible(False)
        search_layout = QHBoxLayout(self._search_bar)
        search_layout.setContentsMargins(20, 4, 20, 4)
        search_layout.setSpacing(6)

        from PySide6.QtWidgets import QLineEdit as _QLE
        self._search_input = _QLE()
        self._search_input.setPlaceholderText("🔍 Search in conversation...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMaximumHeight(26)
        self._search_input.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self._search_input.returnPressed.connect(self._find_next)
        search_layout.addWidget(self._search_input)

        self._search_count = QLabel("")
        self._search_count.setStyleSheet("font-size: 10px; color: #9ca3af;")
        search_layout.addWidget(self._search_count)

        find_prev = QPushButton("◀")
        find_prev.setFixedSize(24, 24)
        find_prev.setStyleSheet("font-size: 10px; border: none;")
        find_prev.clicked.connect(self._find_prev)
        search_layout.addWidget(find_prev)

        find_next = QPushButton("▶")
        find_next.setFixedSize(24, 24)
        find_next.setStyleSheet("font-size: 10px; border: none;")
        find_next.clicked.connect(self._find_next)
        search_layout.addWidget(find_next)

        close_search = QPushButton("✕")
        close_search.setFixedSize(24, 24)
        close_search.setStyleSheet("font-size: 10px; border: none;")
        close_search.clicked.connect(self._hide_search)
        search_layout.addWidget(close_search)

        layout.addWidget(self._search_bar)
        self._search_matches: list = []
        self._search_index = -1

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

        # L1: attachment chips row (hidden until files are attached)
        self._attach_row = QHBoxLayout()
        self._attach_row.setContentsMargins(0, 0, 0, 0)
        self._attachments: list[tuple[str, str]] = []  # (name, path)
        input_layout.addLayout(self._attach_row)

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

        # L1: paperclip for text-file attachments
        from PySide6.QtWidgets import QFileDialog as _QFD  # local: dialog only here
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setMaximumWidth(35)
        self.attach_btn.setMinimumHeight(35)
        self.attach_btn.setToolTip("Attach text files (.txt .md .rst .py .json …)")
        self.attach_btn.clicked.connect(self._pick_attachments)
        controls.addWidget(self.attach_btn)

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

        # Agent preset badge
        self.preset_badge = QLabel("🚀 full_stack")
        self.preset_badge.setObjectName("agentBadge")
        self.preset_badge.setStyleSheet(
            "font-size: 9px; padding: 2px 6px; border-radius: 4px; "
            "background: #374151; color: #d1d5db;"
        )
        self.preset_badge.setVisible(False)
        self.preset_badge.setToolTip("Current agent preset")
        controls.addWidget(self.preset_badge)

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
    # Follow-up suggestion chips (D3)
    # ------------------------------------------------------------------
    def show_followups(self, questions: list) -> None:
        """Render clickable suggested questions above the composer."""
        self.hide_followups()
        if not questions:
            return
        from PySide6.QtWidgets import QFrame
        bar = QFrame()
        bar.setObjectName("followupBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(20, 4, 20, 4)
        row.setSpacing(6)
        for q in questions[:3]:
            btn = QPushButton(q)
            btn.setObjectName("followupChip")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip("Ask this follow-up")
            btn.clicked.connect(lambda _c=False, t=q: self._ask_followup(t))
            row.addWidget(btn, 1)
        self._followup_widget = bar
        self.layout().insertWidget(self.layout().count() - 1, bar)

    def hide_followups(self) -> None:
        w = getattr(self, "_followup_widget", None)
        if w is not None:
            w.setParent(None)
            self._followup_widget = None

    def _ask_followup(self, text: str) -> None:
        if getattr(self, "_generating", False):
            return
        self.hide_followups()
        self.input_text.clear()
        self.message_submitted.emit(text)

    def set_generating(self, generating: bool) -> None:
        """While a reply streams, Send turns into a Stop button.

        Also sets pending state on the current AI bubble (DeepSeek pattern).
        """
        self._generating = bool(generating)
        for _container, bubble in self._bubbles:
            bubble.links_locked = self._generating
        if self._current_ai_bubble is not None:
            self._current_ai_bubble.links_locked = self._generating
            # Set pending state indicator (blue left border while generating)
            self._current_ai_bubble.set_pending_state("generating" if generating else None)
        if generating:
            self.send_btn.setText("⏹ Stop")
            self.send_btn.setEnabled(True)
            self.send_btn.setToolTip("Stop generating")
            self.hide_followups()
        else:
            self.send_btn.setText("Send")
            self.send_btn.setEnabled(bool(self.input_text.toPlainText().strip()))
            self.send_btn.setToolTip("")

    # ------------------------------------------------------------------
    # Message rendering
    # ------------------------------------------------------------------
    def add_user_message(self, text: str) -> None:
        self._add_bubble(text, is_user=True)

    def add_ai_message(self, text: str) -> None:
        """Render a complete AI message, splitting off any thought block."""
        thought, answer = split_reasoning(text)
        if thought:
            self._insert_static_reasoning(thought)
        self._add_bubble(answer or text, is_user=False)

    def _insert_static_reasoning(self, thought: str) -> None:
        """Collapsed reasoning card for replayed/complete messages."""
        block = ReasoningBlock()
        self._apply_block_theme(block)
        block.body.setPlainText(thought)
        block.set_summary("\U0001F4AD Thought process")
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, block)
        self._reasoning_blocks.append(block)

    def _apply_block_theme(self, block: ReasoningBlock) -> None:
        block.set_font_size(self._font_size)
        block.update_style(self._is_dark)

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

    def add_rag_sources(self, chunks: list) -> None:
        """Show RAG source citations after a response that used context."""
        if not chunks:
            return
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
        bar = QFrame()
        bar.setObjectName("ragSourcesBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(20, 4, 20, 4)
        row.setSpacing(6)
        sources_label = QLabel("📚 Sources:")
        sources_label.setObjectName("ragSourcesLabel")
        row.addWidget(sources_label)
        for i, chunk in enumerate(chunks[:3], 1):
            # Shorten path for display
            path = chunk.doc_path.replace("\\", "/").split("/")
            short = path[-1] if path else "doc"
            btn = QPushButton(f"{short}")
            btn.setObjectName("ragSourceChip")
            btn.setToolTip(chunk.text[:200] + "...")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(btn)
        row.addStretch(1)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bar)
        self._maybe_hide_empty_state()
        self.scroll_to_bottom()

    def begin_streaming(self) -> None:
        """Start a new empty AI bubble that tokens will stream into."""
        self._current_ai_text = ""
        self.stopped_in_reasoning = False
        self.last_thinking_ms: int | None = None
        self.hide_followups()
        # Track TTFT (DeepSeek StatsLine pattern)
        import time as _time
        self._ttft_start = _time.monotonic()
        self._parser = ReasoningStreamParser()
        self._reasoning = ReasoningBlock()
        self._apply_block_theme(self._reasoning)
        self._reasoning.begin()
        self._reasoning.setVisible(False)  # until the first thought arrives

        # Hide the empty pill until the first token arrives, so no empty
        # card flashes on slow first tokens.
        self._current_ai_bubble = ChatBubble("", is_user=False)
        self._apply_bubble_theme(self._current_ai_bubble)
        self._current_ai_bubble.setVisible(False)

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, self._reasoning)
        self._reasoning_blocks.append(self._reasoning)
        container = _BubbleRow(self._current_ai_bubble, is_user=False)
        self._current_ai_bubble.links_locked = True  # unlock when done
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self._bubbles.append((container, self._current_ai_bubble))
        self._maybe_hide_empty_state()
        self.scroll_to_bottom()

    def stream_token(self, token: str) -> None:
        if self._current_ai_bubble is None:
            return
        parser = self._parser or ReasoningStreamParser()
        for kind, text in parser.feed(token):
            if kind == "thought":
                if not text:
                    continue
                if self._reasoning is not None and not self._reasoning.isVisible():
                    self._reasoning.setVisible(True)
                if self._reasoning is not None:
                    self._reasoning.append_thought(text)
            else:
                # First answer token: collapse the thinking block.
                if self._reasoning is not None and not self._reasoning._finished:
                    self._reasoning.finish_thinking()
                self._current_ai_bubble.setVisible(True)
                self._current_ai_text += text
                self._current_ai_bubble.update_text(
                    format_answer(self._current_ai_text))
        self.scroll_to_bottom()

    def finish_streaming(self) -> str:
        """Finalize the streaming bubble; returns the clean answer text."""
        # Record TTFT if we have it
        if self._ttft_start is not None:
            import time as _time
            ttft_ms = int((_time.monotonic() - self._ttft_start) * 1000)
            self._last_ttft_ms = ttft_ms
            self._ttft_start = None
        had_thoughts = (
            self._reasoning is not None and bool(self._reasoning.body.text().strip())
        )
        parser = self._parser
        finish_events = parser.finish() if parser is not None else []
        was_plain = getattr(parser, "final_state", "") == "prologue"
        self._parser = None
        for kind, text in finish_events:
            if kind == "answer" or was_plain:
                if text:
                    self._current_ai_bubble.setVisible(True)
                    self._current_ai_text += text
                    self._current_ai_bubble.update_text(
                        format_answer(self._current_ai_text))
            else:
                if self._reasoning is not None and text:
                    self._reasoning.append_thought(text)
                    self._reasoning.setVisible(True)
        # Plain reply: everything streamed "as thought" was actually the
        # answer - move it out of the thinking card into the bubble.
        if was_plain:
            pending = ""
            if self._reasoning is not None:
                pending = self._reasoning.body.text()
                self._reasoning.setParent(None)
                if self._reasoning in self._reasoning_blocks:
                    self._reasoning_blocks.remove(self._reasoning)
                self._reasoning = None
            self._current_ai_text = pending + self._current_ai_text
            if self._current_ai_text and self._current_ai_bubble is not None:
                self._current_ai_bubble.setVisible(True)
                self._current_ai_bubble.update_text(format_answer(self._current_ai_text))
        # Generation that ends inside the think block means the token
        # budget ran out before any answer was produced.
        self.stopped_in_reasoning = (
            had_thoughts and not was_plain and not self._current_ai_text.strip()
        )
        if self._reasoning is not None:
            if self._reasoning.body.text().strip():
                dur = self._reasoning._duration_secs
                self.last_thinking_ms = int(dur * 1000) if dur else None
                self._reasoning.finish_thinking()
            else:
                # Plain model output - drop the unused thinking card.
                self._reasoning.setParent(None)
                if self._reasoning in self._reasoning_blocks:
                    self._reasoning_blocks.remove(self._reasoning)
            self._reasoning = None
        for _c, bubble in self._bubbles:  # unlock links once done
            bubble.links_locked = False
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
        self._parser = None
        self._reasoning = None
        self._reasoning_blocks.clear()
        if hasattr(self, "agent_panel"):
            self.agent_panel.clear()
        # Remove every remaining widget (system labels included); the last
        # layout item is the trailing stretch.
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._maybe_hide_empty_state()

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

    def set_preset_badge(self, preset: str) -> None:
        """Update the preset badge text."""
        icons = {
            "research": "🔍", "code_review": "📝", "refactor": "♻️",
            "debug": "🐛", "full_stack": "🚀", "quick_fix": "⚡",
        }
        icon = icons.get(preset, "🤖")
        self.preset_badge.setText(f"{icon} {preset}")
        self.preset_badge.setVisible(True)


    def get_workspace(self) -> str:
        return self.workspace_combo.currentText().strip()

    def set_workspace(self, path: str) -> None:
        self.workspace_combo.setCurrentText(path)
        # Initialize or update autocomplete with workspace
        if path and self._autocomplete is None:
            try:
                from ggufloader.widgets.smart_autocomplete import SmartAutocomplete
                from pathlib import Path as _P
                self._autocomplete = SmartAutocomplete(_P(path), self)
                self._autocomplete.scan_workspace()
                self._autocomplete.suggestion_selected.connect(self._on_autocomplete_select)
            except Exception:
                pass
        elif path and self._autocomplete is not None:
            from pathlib import Path as _P
            self._autocomplete.workspace = _P(path)
            self._autocomplete.scan_workspace()

    def _on_autocomplete_select(self, text: str) -> None:
        """Handle autocomplete suggestion selection."""
        if text.startswith("/"):
            # It's a slash command - execute it directly
            response = self._slash_commands.handle(text)
            if response:
                self.add_system_message(response)
        else:
            # Insert into input
            self.input_text.setPlainText(text)

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
        for block in self._reasoning_blocks:
            block.set_font_size(size)

    def apply_theme(self, is_dark: bool) -> None:
        self._is_dark = is_dark
        for _container, bubble in self._bubbles:
            bubble.update_style(is_dark)
        for block in self._reasoning_blocks:
            block.update_style(is_dark)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _submit(self) -> None:
        if getattr(self, "_generating", False):
            self.stop_requested.emit()
            return
        text = self.input_text.toPlainText().strip()
        attachments = self._attachment_text()
        if not text and not attachments:
            return
        if not text and attachments:
            text = "Please review the attached file(s)."
        self.input_text.clear()
        self.clear_attachments()

        # Handle slash commands (Aider pattern)
        if text.startswith("/"):
            response = self._slash_commands.handle(text)
            if response:
                self.add_system_message(response)
                return

        self.message_submitted.emit(text + attachments)

    def _on_input_changed(self) -> None:
        if getattr(self, "_generating", False):
            return  # Stop button stays enabled regardless of text
        has_text = bool(self.input_text.toPlainText().strip())
        self.send_btn.setEnabled(has_text)
        # Show autocomplete for slash commands
        if self._autocomplete is not None:
            text = self.input_text.toPlainText()
            if text.startswith("/"):
                suggestions = self._autocomplete.get_suggestions(text, limit=8)
                if suggestions:
                    self._autocomplete.show_suggestions(suggestions)
                    # Position below input
                    pos = self.input_text.mapToGlobal(self.input_text.rect().bottomLeft())
                    self._autocomplete.move(self.mapFromGlobal(pos))
                    self._autocomplete.show()
                else:
                    self._autocomplete.setVisible(False)
            else:
                self._autocomplete.setVisible(False)

    def copy_conversation(self) -> str:
        """Whole transcript as text (GPT4All's copy-conversation parity)."""
        lines = []
        for _container, bubble in self._bubbles:
            who = "You" if bubble.is_user else "AI"
            lines.append(f"{who}: {bubble.text}")
        return "\n\n".join(lines)

    def pop_last_exchange(self) -> str | None:
        """Remove the newest user+assistant pair from the transcript.

        Returns the popped user text (for edit/regenerate), or None when
        there is no complete exchange to pop.
        """
        if not self._bubbles:
            return None
        # Expect [..., user, assistant]
        if self._bubbles[-1][1].is_user:
            return None
        removed_user_text: str | None = None
        while self._bubbles:
            container, bubble = self._bubbles.pop()
            container.setParent(None)
            if bubble.is_user:
                removed_user_text = bubble.text
                break
        self._maybe_hide_empty_state()
        return removed_user_text

    def refill_input(self, text: str) -> None:
        """Put *text* back into the composer for editing."""
        self.input_text.setPlainText(text)
        self.input_text.setFocus()
        self.send_btn.setEnabled(bool(text.strip()))

    # ------------------------------------------------------------------
    # L1: attachments
    # ------------------------------------------------------------------
    MAX_ATTACHMENT_CHARS = 20_000

    def _pick_attachments(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach text files", "",
            "Text files (*.txt *.md *.rst *.py *.json *.csv *.log *.yaml *.yml);;All files (*)",
        )
        for p in paths:
            name = Path(p).name
            if any(existing == name for existing, _p in self._attachments):
                continue
            self._attachments.append((name, p))
            chip = QPushButton(f"📄 {name}  ✕")
            chip.setObjectName("attachmentChip")
            chip.setToolTip(p)
            chip.setFlat(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _c=False, n=name: self._remove_attachment(n))
            self._attach_row.addWidget(chip)
        self._attach_row.parentWidget().updateGeometry()

    def _remove_attachment(self, name: str) -> None:
        self._attachments = [(n, p) for n, p in self._attachments if n != name]
        while self._attach_row.count():
            item = self._attach_row.takeAt(0)
            w = item.widget()
            if w is not None and (w.text() == f"📄 {name}  ✕"):
                w.setParent(None)
                break

    def _attachment_text(self) -> str:
        """Render attachments as fenced blocks appended to the message."""
        blocks = []
        remaining = self.MAX_ATTACHMENT_CHARS
        for name, path in list(self._attachments):
            try:
                content = Path(path).read_text(encoding="utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001 - unreadable => note & skip
                blocks.append(f"--- Attached file: {name} ---\n(unreadable: {e})")
                continue
            content = content[:remaining]
            remaining -= len(content)
            suffix = "\n…(truncated)" if remaining <= 0 else ""
            blocks.append(f"--- Attached file: {name} ---\n```text\n{content}{suffix}\n```")
            if remaining <= 0:
                break
        return "".join("\n\n" + b for b in blocks)

    def clear_attachments(self) -> None:
        self._attachments.clear()
        while self._attach_row.count():
            item = self._attach_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def set_feedback_on_bubble(self, bubble: ChatBubble, status: str) -> None:
        """K5 entry point used by MainWindow after persisting feedback."""
        # Currently a no-op hook; visual state lives in session data.
        _ = bubble, status

    def _on_agent_toggled(self, checked: bool) -> None:
        self.is_agent_mode = checked
        self.agent_mode_btn.setText("🤖 Agent Mode: ON" if checked else "🤖 Agent Mode: OFF")
        self.agent_mode_toggled.emit(checked)

    def set_agent_mode(self, on: bool) -> None:
        """Programmatic toggle (no signal) - used when restoring sessions."""
        self.agent_mode_btn.blockSignals(True)
        self.is_agent_mode = bool(on)
        self.agent_mode_btn.setChecked(bool(on))
        self.agent_mode_btn.setText("🤖 Agent Mode: ON" if on else "🤖 Agent Mode: OFF")
        self.agent_mode_btn.blockSignals(False)

    def _add_bubble(self, text: str, is_user: bool) -> None:
        bubble = ChatBubble(text, is_user)
        self._apply_bubble_theme(bubble)
        if not is_user:
            bubble.on_regenerate = self.regenerate_requested.emit
            bubble.on_feedback = self.feedback_requested.emit
            bubble.on_delete = lambda t=text: self.delete_message_requested.emit(t)
        else:
            bubble.on_edit = self.edit_last_requested.emit
            bubble.on_delete = lambda t=text: self.delete_message_requested.emit(t)

        container = _BubbleRow(bubble, is_user, is_rtl=bubble.is_rtl)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self._bubbles.append((container, bubble))
        # Hide the empty state only after the bubble is registered, so the
        # very first user message swaps the hero out immediately.
        self._maybe_hide_empty_state()
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
        has_bubbles = bool(self._bubbles) or self._current_ai_bubble is not None
        # System labels live in the layout but not in _bubbles; the last
        # layout item is the trailing stretch.
        has_content = has_bubbles or self.chat_layout.count() > 1
        self.chat_stack.setCurrentIndex(1 if has_content else 0)

    def scroll_to_bottom(self) -> None:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    # ------------------------------------------------------------------
    # Export conversation (Aider markdown export pattern)
    # ------------------------------------------------------------------
    def export_conversation(self) -> str:
        """Export the full conversation as a markdown file."""
        lines = ["# GGUF Loader Conversation\n"]
        from datetime import datetime
        lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        lines.append("---\n")
        for _container, bubble in self._bubbles:
            if bubble.is_user:
                lines.append(f"## You\n\n{bubble.text}\n")
            else:
                lines.append(f"## AI\n\n{bubble.text}\n")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Chat search (Ctrl+F)
    # ------------------------------------------------------------------
    def toggle_search(self) -> None:
        """Toggle the search bar visibility."""
        if self._search_bar.isVisible():
            self._hide_search()
        else:
            self._show_search()

    def _show_search(self) -> None:
        self._search_bar.setVisible(True)
        self._search_input.setFocus()
        self._search_input.selectAll()

    def _hide_search(self) -> None:
        self._search_bar.setVisible(False)
        self._search_input.clear()
        self._search_count.setText("")
        self._clear_search_highlights()

    def _find_next(self) -> None:
        self._do_search(forward=True)

    def _find_prev(self) -> None:
        self._do_search(forward=False)

    def _do_search(self, forward: bool = True) -> None:
        """Search through all bubbles for the query text."""
        query = self._search_input.text().strip()
        if not query:
            self._search_count.setText("")
            return

        # Collect all text from bubbles
        self._search_matches = []
        for i, (_container, bubble) in enumerate(self._bubbles):
            text = bubble.text.lower()
            if query.lower() in text:
                self._search_matches.append(i)

        if not self._search_matches:
            self._search_count.setText("No matches")
            return

        # Move to next/prev match
        if forward:
            self._search_index = (self._search_index + 1) % len(self._search_matches)
        else:
            self._search_index = (self._search_index - 1) % len(self._search_matches)

        match_idx = self._search_matches[self._search_index]
        self._search_count.setText(f"{self._search_index + 1}/{len(self._search_matches)}")

        # Scroll to the matching bubble
        if 0 <= match_idx < len(self._bubbles):
            container, _ = self._bubbles[match_idx]
            self.chat_scroll.ensureWidgetVisible(container)

    def _clear_search_highlights(self) -> None:
        self._search_matches = []
        self._search_index = -1

