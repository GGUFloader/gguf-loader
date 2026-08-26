"""
AgentPanel - Structured live transcript for agent runs.

Renders the agent's activity as cards instead of free-text status lines:
user/AI bubbles (same ChatGPT-style look as the main chat), step chips,
tool result cards, and approval cards with Allow/Deny buttons. The panel
is deliberately dumb - MainWindow feeds it events from AgentService
signals.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ggufloader.config import CHAT_BUBBLE_FONT_SIZE, FONT_FAMILY
from ggufloader.core.reasoning import ReasoningStreamParser, format_answer, split_reasoning
from ggufloader.widgets.chat_bubble import ChatBubble, _BubbleRow
from ggufloader.widgets.reasoning_block import ReasoningBlock


class AgentPanel(QWidget):
    """Structured live transcript for agent runs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("agentRoot")
        self._is_dark = False
        self._font_size = CHAT_BUBBLE_FONT_SIZE
        self._current_ai_bubble: ChatBubble | None = None
        self._current_ai_text = ""
        self._bubbles: list[tuple[QWidget, ChatBubble]] = []
        self._parser: ReasoningStreamParser | None = None
        self._reasoning: ReasoningBlock | None = None
        self._reasoning_blocks: list[ReasoningBlock] = []
        self._pending_approvals: list[tuple[QFrame, QLabel, QPushButton, QPushButton]] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.container = QWidget()
        self.col = QVBoxLayout(self.container)
        self.col.setSpacing(8)
        self.col.setContentsMargins(20, 20, 20, 20)
        self.col.addStretch()
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    # ------------------------------------------------------------------
    # Messages (mirrors ChatPanel's streaming API)
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
        block = ReasoningBlock()
        block.set_font_size(self._font_size)
        block.update_style(self._is_dark)
        block.body.setPlainText(thought)
        block.set_summary("\U0001F4AD Thought process")
        self.col.insertWidget(self.col.count() - 1, block)
        self._reasoning_blocks.append(block)

    def begin_streaming(self) -> None:
        """Start a new empty AI bubble that tokens will stream into."""
        self._current_ai_text = ""
        self._parser = ReasoningStreamParser()
        self._reasoning = ReasoningBlock()
        self._reasoning.set_font_size(self._font_size)
        self._reasoning.update_style(self._is_dark)
        self._reasoning.begin()
        self._reasoning.setVisible(False)  # until the first thought arrives
        self._current_ai_bubble = ChatBubble("", is_user=False)
        self._apply_bubble_theme(self._current_ai_bubble)
        # Hidden until the first token arrives (no empty card flash).
        self._current_ai_bubble.setVisible(False)
        row = _BubbleRow(self._current_ai_bubble, is_user=False)
        self.col.insertWidget(self.col.count() - 1, self._reasoning)
        self._reasoning_blocks.append(self._reasoning)
        self.col.insertWidget(self.col.count() - 1, row)
        self._bubbles.append((row, self._current_ai_bubble))
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
                if self._reasoning is not None and not self._reasoning._finished:
                    self._reasoning.finish_thinking()
                self._current_ai_bubble.setVisible(True)
                self._current_ai_text += text
                self._current_ai_bubble.update_text(
                    format_answer(self._current_ai_text))
        self.scroll_to_bottom()

    def finish_streaming(self) -> str:
        """Finalize the streaming bubble; returns the clean answer text."""
        if self._parser is not None:
            for kind, text in self._parser.finish():
                if kind == "thought":
                    if self._reasoning is not None and text:
                        self._reasoning.append_thought(text)
                        self._reasoning.setVisible(True)
                else:
                    self._current_ai_bubble.setVisible(True)
                    self._current_ai_text += text
                    self._current_ai_bubble.update_text(
                        format_answer(self._current_ai_text))
            self._parser = None
        if self._reasoning is not None:
            if self._reasoning.body.text().strip():
                self._reasoning.finish_thinking()
            else:
                # Plain model output - drop the unused thinking card.
                self._reasoning.setParent(None)
                if self._reasoning in self._reasoning_blocks:
                    self._reasoning_blocks.remove(self._reasoning)
            self._reasoning = None
        text = self._current_ai_text.strip()
        self._current_ai_bubble = None
        self._current_ai_text = ""
        return text

    # ------------------------------------------------------------------
    # Transcript events
    # ------------------------------------------------------------------
    def add_status(self, text: str) -> None:
        """Centered status line (or a step chip for '▶ Step N/M')."""
        if not text:
            return
        if text.startswith("▶ Step"):
            label = QLabel(text)
            label.setObjectName("stepChip")
            label.setAlignment(Qt.AlignCenter)
        else:
            label = QLabel(text)
            label.setObjectName("systemMessage")
            label.setAlignment(Qt.AlignCenter)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            font = QFont(FONT_FAMILY, 11)
            font.setItalic(True)
            label.setFont(font)
        self.col.insertWidget(self.col.count() - 1, label)
        self.scroll_to_bottom()

    def add_tool_card(self, result: dict) -> None:
        """Render one tool execution as a result card."""
        card = QFrame()
        card.setObjectName("toolCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(4)

        tool = result.get("tool_name", "tool")
        ok = result.get("status") == "success"
        title = QLabel(("✅ " if ok else "❌ ") + self._tool_title(tool, result))
        title.setObjectName("toolCardTitle")
        v.addWidget(title)

        summary = self._summarize(result)
        if summary:
            sub = QLabel(summary)
            sub.setObjectName("toolCardSub")
            sub.setWordWrap(True)
            v.addWidget(sub)

        detail = self._detail_text(result)
        if detail:
            mono = QLabel(detail)
            mono.setObjectName("monoText")
            mono.setWordWrap(True)
            mono.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            v.addWidget(mono)

        self.col.insertWidget(self.col.count() - 1, card)
        self.scroll_to_bottom()

    def add_approval_card(self, payload: dict, waiter: Any) -> None:
        """Render an approval request with Allow/Deny buttons.

        The buttons resolve the caller-provided *waiter* (an
        ApprovalWaiter) so the worker thread resumes the graph.
        """
        card = QFrame()
        card.setObjectName("approvalCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(6)

        title = QLabel("🔐 Approval required")
        title.setObjectName("approvalTitle")
        v.addWidget(title)

        desc = QLabel(payload.get("description", "Run this command?"))
        desc.setObjectName("toolCardSub")
        desc.setWordWrap(True)
        v.addWidget(desc)

        command_text = self._command_text(payload)
        if command_text:
            cmd = QLabel(command_text)
            cmd.setObjectName("monoText")
            cmd.setWordWrap(True)
            cmd.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            v.addWidget(cmd)

        hint = QLabel("Waiting for your decision…")
        hint.setObjectName("toolCardSub")
        v.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        allow = QPushButton("Allow")
        allow.setObjectName("primaryButton")
        deny = QPushButton("Deny")
        deny.setObjectName("dangerButton")
        buttons.addWidget(allow)
        buttons.addWidget(deny)
        v.addLayout(buttons)

        def resolve(approved: bool) -> None:
            waiter.resolve(approved)
            allow.setEnabled(False)
            deny.setEnabled(False)
            allow.setVisible(False)
            deny.setVisible(False)
            hint.setText("✅ Approved — running…" if approved else "⛔ Denied")
            self._pending_approvals = [
                entry for entry in self._pending_approvals if entry[0] is not card
            ]

        allow.clicked.connect(lambda: resolve(True))
        deny.clicked.connect(lambda: resolve(False))

        self.col.insertWidget(self.col.count() - 1, card)
        self._pending_approvals.append((card, hint, allow, deny))
        self.scroll_to_bottom()

    def mark_cancelled(self) -> None:
        """Visually close any unanswered approval cards (run was cancelled)."""
        for _card, hint, allow, deny in self._pending_approvals:
            allow.setEnabled(False)
            deny.setEnabled(False)
            hint.setText("⛔ Cancelled")
        self._pending_approvals.clear()

    def clear(self) -> None:
        """Remove every transcript element."""
        while self.col.count() > 1:  # keep the trailing stretch
            item = self.col.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._bubbles.clear()
        self._current_ai_bubble = None
        self._current_ai_text = ""
        self._parser = None
        self._reasoning = None
        self._reasoning_blocks.clear()
        self._pending_approvals.clear()

    # ------------------------------------------------------------------
    # Theming / sizing
    # ------------------------------------------------------------------
    def apply_theme(self, is_dark: bool) -> None:
        self._is_dark = is_dark
        for _row, bubble in self._bubbles:
            bubble.update_style(is_dark)
        for block in self._reasoning_blocks:
            block.update_style(is_dark)

    def apply_font_size(self, size: int) -> None:
        self._font_size = size
        for _row, bubble in self._bubbles:
            bubble.set_font_size(size)
        for block in self._reasoning_blocks:
            block.set_font_size(size)

    def _apply_bubble_theme(self, bubble: ChatBubble) -> None:
        bubble.set_font_size(self._font_size)
        bubble.update_style(self._is_dark)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _add_bubble(self, text: str, is_user: bool) -> None:
        bubble = ChatBubble(text, is_user)
        self._apply_bubble_theme(bubble)
        row = _BubbleRow(bubble, is_user, is_rtl=bubble.is_rtl)
        self.col.insertWidget(self.col.count() - 1, row)
        self._bubbles.append((row, bubble))
        self.scroll_to_bottom()

    def _tool_title(self, tool: str, result: dict) -> str:
        path = result.get("path")
        if path:
            return f"{tool} — {path}"
        return tool

    def _summarize(self, result: dict) -> str:
        if result.get("status") == "success":
            tool = result.get("tool_name", "")
            if tool == "list_directory":
                return f"Found {len(result.get('result', []))} items"
            if tool == "search_files":
                return f"Found {result.get('total_matches', 0)} matches"
            text = result.get("result")
            if isinstance(text, str) and text:
                return text
            return "Done"
        return result.get("error", "Failed")

    def _detail_text(self, result: dict) -> str:
        tool = result.get("tool_name", "")
        text = result.get("result")
        if tool in ("run_command", "git") and isinstance(text, str) and text.strip():
            return text[:500] + ("…" if len(text) > 500 else "")
        if tool == "read_file" and isinstance(text, str):
            return text[:1000] + ("…" if len(text) > 1000 else "")
        if tool == "list_directory" and isinstance(text, list):
            return ", ".join(str(item.get("name", "?")) for item in text[:30])
        if tool == "search_files" and isinstance(text, list):
            return ", ".join(str(p) for p in text[:30])
        return ""

    def _command_text(self, payload: dict) -> str:
        call = payload.get("call") or {}
        params = call.get("parameters") or {}
        tool = call.get("tool", "")
        if tool == "run_command":
            return params.get("command", "")
        if tool == "git":
            args = params.get("args") or []
            return "git " + " ".join(str(a) for a in args)
        return ""

    def scroll_to_bottom(self) -> None:
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))
