"""ReasoningBlock - ChatGPT-style collapsible "thought process" card.

Sits above an assistant bubble: while the model is thinking it shows the
live reasoning stream under a "💭 Thinking…" header; once the answer
starts it collapses to a one-line summary that can be clicked to expand.

The body is sized explicitly (like ChatBubble.fit_width): a read-only
QTextEdit reports a near-zero sizeHint, so without manual height math the
streaming text would be invisible.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from ggufloader.config import FONT_FAMILY
from ggufloader.ui.theme import DARK_TOKENS, LIGHT_TOKENS
from ggufloader.widgets.chat_bubble import _BubbleText

_MAX_BODY_HEIGHT = 280   # long thoughts scroll instead of eating the screen


class ReasoningBlock(QFrame):
    """Collapsible container for a model's chain-of-thought."""

    _PAD_X = 30  # horizontal chrome around the body (padding + border)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("reasoningBlock")
        self._is_dark = False
        self._font_size = 12
        self._started_at: float | None = None
        self._duration_secs: float | None = None
        self._finished = False
        self._collapsed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toggle_btn = QPushButton("\u25BE \U0001F4AD Thinking\u2026")
        self.toggle_btn.setObjectName("reasoningToggle")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setStyleSheet("text-align: left;")
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        self.body = _BubbleText("")
        self.body.setObjectName("reasoningBody")
        self.body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.body)

        self.update_style(False)

    # ------------------------------------------------------------------
    # Streaming API
    # ------------------------------------------------------------------
    def begin(self) -> None:
        self._started_at = time.monotonic()

    def append_thought(self, text: str) -> None:
        if not text:
            return
        self.body.setPlainText(self.body.text() + text)
        self._scroll_body_to_bottom()
        self.relayout()

    def finish_thinking(self) -> None:
        """Thinking is over - collapse and show the elapsed time."""
        if self._finished:
            return
        self._finished = True
        if self._started_at is not None:
            self._duration_secs = time.monotonic() - self._started_at
        if not self.body.text().strip():
            self.set_summary("\U0001F4AD Thought process")
        self.set_collapsed(True)

    def summary_label(self) -> str:
        if self._duration_secs is not None and self._duration_secs >= 1:
            return f"\U0001F4AD Thought for {int(round(self._duration_secs))}s"
        return "\U0001F4AD Thought process"

    def set_summary(self, text: str) -> None:
        """Static label for replayed sessions (no timing known)."""
        self._finished = True
        self.toggle_btn.setText(text or "\U0001F4AD Thought process")

    # ------------------------------------------------------------------
    # Collapse behaviour (ChatGPT-style minimize)
    # ------------------------------------------------------------------
    def _on_toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        """Minimize to the header line, or expand the full thought text."""
        self._collapsed = bool(collapsed)
        arrow = "\u25B8" if self._collapsed else "\u25BE"
        label = self.summary_label() if self._finished else "\U0001F4AD Thinking\u2026"
        self.toggle_btn.setText(f"{arrow} {label}")
        self.body.setVisible(not self._collapsed)
        self.relayout()

    def _apply_collapse(self) -> None:
        self.set_collapsed(self._collapsed)

    def _scroll_body_to_bottom(self) -> None:
        bar = self.body.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ------------------------------------------------------------------
    # Sizing (explicit - QTextEdit gives useless sizeHints)
    # ------------------------------------------------------------------
    def relayout(self) -> None:
        header_h = self.toggle_btn.sizeHint().height()
        if header_h <= 0:
            header_h = self.toggle_btn.fontMetrics().height() + 16

        if self._collapsed or not self.body.isVisible():
            self.body.setFixedHeight(0)
            self.setFixedHeight(max(header_h + 2, 30))
            return

        width = max(self.width() - self._PAD_X - 2, 60)
        body_h = self.body.heightForWidth(width)
        if body_h <= 0:
            body_h = self.body.fontMetrics().height() + 20
        body_h = min(int(body_h), _MAX_BODY_HEIGHT)
        self.body.setFixedHeight(body_h)
        self.setFixedHeight(header_h + body_h + 2)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self.relayout()

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------
    def update_style(self, is_dark: bool) -> None:
        self._is_dark = is_dark
        t = DARK_TOKENS if is_dark else LIGHT_TOKENS
        self.setStyleSheet(f"""
            QFrame#reasoningBlock {{
                background-color: {t["elevated"]};
                border: 1px solid {t["border"]};
                border-radius: 12px;
            }}
            QPushButton#reasoningToggle {{
                color: {t["textMuted"]};
                background: transparent;
                border: none;
                text-align: left;
                padding: 8px 14px;
                font-size: {self._font_size}px;
            }}
            QTextEdit#reasoningBody {{
                color: {t["textMuted"]};
                font-size: {max(self._font_size - 2, 10)}px;
                font-style: italic;
                padding: 0px 14px 8px 14px;
                background: transparent;
                border: none;
            }}
        """)
        font = QFont(FONT_FAMILY, self._font_size)
        self.toggle_btn.setFont(font)
        body_font = QFont(FONT_FAMILY, max(self._font_size - 2, 9))
        body_font.setItalic(True)
        self.body.setFont(body_font)
        self.relayout()

    def set_font_size(self, size: int) -> None:
        self._font_size = max(int(size) - 2, 10)
        self.update_style(self._is_dark)
