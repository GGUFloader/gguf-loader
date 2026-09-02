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
from ggufloader.widgets.agent_metrics_bar import AgentMetricsBar
from ggufloader.widgets.chat_bubble import ChatBubble, _BubbleRow
from ggufloader.widgets.reasoning_block import ReasoningBlock


class AgentPanel(QWidget):
    """Structured live transcript for agent runs.

    Features:
    - ConfirmGroup batch approval (Aider pattern)
    - Risk badges on tool cards (OpenHands pattern)
    - DisclosureRow for collapsible sections (DeepSeek pattern)
    """

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
        # ConfirmGroup state (Aider pattern)
        self._confirm_group_preference: str | None = None  # "all" | "skip" | None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Live metrics bar (shown during agent runs)
        self.metrics_bar = AgentMetricsBar()
        layout.addWidget(self.metrics_bar)

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
        # Add copy button after each AI response
        self._add_copy_response_button(answer or text)

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
        max_steps = 8
        engine = getattr(self, "_current_engine", None)
        if engine is not None and hasattr(engine, "max_steps"):
            max_steps = engine.max_steps
        self.metrics_bar.start(max_steps=max_steps)
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
        self.metrics_bar.stop()
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
        # Plain reply: relocate streamed "thought" text into the bubble.
        if was_plain and self._reasoning is not None:
            pending = self._reasoning.body.text()
            self._reasoning.setParent(None)
            if self._reasoning in self._reasoning_blocks:
                self._reasoning_blocks.remove(self._reasoning)
            self._reasoning = None
            self._current_ai_text = pending + self._current_ai_text
            if self._current_ai_text and self._current_ai_bubble is not None:
                self._current_ai_bubble.setVisible(True)
                self._current_ai_bubble.update_text(format_answer(self._current_ai_text))
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
    def _add_copy_response_button(self, text: str) -> None:
        """Add a small copy button after an AI response."""
        btn = QPushButton("📋 Copy Response")
        btn.setObjectName("copyResponseBtn")
        btn.setFixedHeight(24)
        btn.setStyleSheet("font-size: 10px; padding: 2px 8px; border: 1px solid #4b5563; border-radius: 4px; background: transparent; color: #9ca3af;")
        btn.setCursor(Qt.PointingHandCursor)

        def do_copy():
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            btn.setText("✅ Copied!")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: btn.setText("📋 Copy Response"))

        btn.clicked.connect(do_copy)
        self.col.insertWidget(self.col.count() - 1, btn)

    def add_status(self, text: str) -> None:
        """Centered status line (or a step chip for '▶ Step N/M')."""
        # Update metrics bar from step status
        if text.startswith("▶ Step"):
            try:
                parts = text.split()
                step_part = parts[1]  # "Step"
                nums = parts[2].split("/")  # "3/8"
                if len(nums) == 2:
                    self.metrics_bar.update_steps(int(nums[0]), int(nums[1]))
            except (IndexError, ValueError):
                pass
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

    def add_tool_card(self, result: dict, risk: str = "low") -> None:
        """Render one tool execution as a result card.

        Args:
            result: Tool execution result dict
            risk: Risk level from _assess_risk() (low/medium/high)
        """
        card = QFrame()
        card.setObjectName("toolCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(4)

        tool = result.get("tool_name", "tool")
        ok = result.get("status") == "success"

        # Header row with title + risk badge (OpenHands SecurityRisk pattern)
        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel(("✅ " if ok else "❌ ") + self._tool_title(tool, result))
        title.setObjectName("toolCardTitle")
        header.addWidget(title)
        header.addStretch()

        # Risk badge
        risk_colors = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444"}
        risk_labels = {"low": "🟢 Low", "medium": "🟡 Medium", "high": "🔴 High"}
        if risk in risk_colors:
            risk_label = QLabel(risk_labels.get(risk, risk))
            risk_label.setStyleSheet(
                f"color: {risk_colors[risk]}; font-size: 10px; "
                f"padding: 2px 6px; border-radius: 4px; "
                f"background: {risk_colors[risk]}22;"
            )
            header.addWidget(risk_label)

        v.addLayout(header)

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

        Supports ConfirmGroup batch approval (Aider pattern):
        - If user previously selected "All", auto-approve without showing card
        - If user previously selected "Skip", auto-deny without showing card
        - Otherwise show card with Allow/Deny/All/Skip/Don't-ask-again buttons
        """
        # Check ConfirmGroup preference (Aider pattern)
        if self._confirm_group_preference == "all":
            waiter.resolve(True)
            return
        if self._confirm_group_preference == "skip":
            waiter.resolve(False)
            return

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

        # ConfirmGroup buttons (Aider pattern: Allow/Deny/All/Skip/Don't)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        allow = QPushButton("Allow")
        allow.setObjectName("primaryButton")
        deny = QPushButton("Deny")
        deny.setObjectName("dangerButton")
        all_btn = QPushButton("All")
        all_btn.setToolTip("Allow this and all subsequent approvals")
        all_btn.setObjectName("gpuInstallBtn")
        skip_btn = QPushButton("Skip All")
        skip_btn.setToolTip("Deny this and all subsequent approvals")
        skip_btn.setObjectName("gpuInstallBtn")
        buttons.addWidget(allow)
        buttons.addWidget(deny)
        buttons.addWidget(all_btn)
        buttons.addWidget(skip_btn)
        v.addLayout(buttons)

        def resolve(approved: bool) -> None:
            waiter.resolve(approved)
            allow.setEnabled(False)
            deny.setEnabled(False)
            all_btn.setEnabled(False)
            skip_btn.setEnabled(False)
            allow.setVisible(False)
            deny.setVisible(False)
            all_btn.setVisible(False)
            skip_btn.setVisible(False)
            hint.setText("✅ Approved — running…" if approved else "⛔ Denied")
            self._pending_approvals = [
                entry for entry in self._pending_approvals if entry[0] is not card
            ]

        def resolve_all() -> None:
            self._confirm_group_preference = "all"
            waiter.resolve(True)
            # Auto-approve all pending approvals
            for _card, _hint, allow_e, deny_e in self._pending_approvals:
                allow_e.setEnabled(False)
                deny_e.setEnabled(False)
                allow_e.setVisible(False)
                deny_e.setVisible(False)
            self._pending_approvals.clear()

        def resolve_skip_all() -> None:
            self._confirm_group_preference = "skip"
            waiter.resolve(False)
            # Auto-deny all pending approvals
            for _card, _hint, allow_e, deny_e in self._pending_approvals:
                allow_e.setEnabled(False)
                deny_e.setEnabled(False)
                allow_e.setVisible(False)
                deny_e.setVisible(False)
            self._pending_approvals.clear()

        allow.clicked.connect(lambda: resolve(True))
        deny.clicked.connect(lambda: resolve(False))
        all_btn.clicked.connect(resolve_all)
        skip_btn.clicked.connect(resolve_skip_all)

        self.col.insertWidget(self.col.count() - 1, card)
        self._pending_approvals.append((card, hint, allow, deny))
        self.scroll_to_bottom()

    def update_metrics(self, **kwargs) -> None:
        """Update the metrics bar from external data."""
        if "tokens" in kwargs:
            self.metrics_bar.update_tokens(kwargs["tokens"])
        if "retries" in kwargs:
            self.metrics_bar.update_retries(kwargs["retries"])
        if "context_pct" in kwargs:
            self.metrics_bar.update_context(kwargs["context_pct"])
        if "steps" in kwargs:
            self.metrics_bar.update_steps(kwargs["steps"])

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
