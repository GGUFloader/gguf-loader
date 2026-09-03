"""
AgentMetricsBar - Compact live metrics display during agent runs.

Shows: steps, tokens, time, retries, context usage.
Lives at the top of the AgentPanel during active runs.
Disappears when the agent finishes.

Pattern from: DeepSeek StatsLine + OpenHands status bar.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class AgentMetricsBar(QWidget):
    """Compact horizontal metrics bar for live agent status.

    Shows: Steps | Tokens | Time | Retries | Context
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("agentMetricsBar")
        self._start_time: float = 0
        self._steps = 0
        self._max_steps: int | None = None  # None = no plan total known
        self._tokens = 0
        self._retries = 0
        self._context_pct = 0
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._update_time)
        self._build_ui()
        self.setVisible(False)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(12)

        font = QFont(FONT_FAMILY, 10)

        self._steps_label = QLabel("Steps: 0/0")
        self._steps_label.setFont(font)
        self._steps_label.setStyleSheet("color: #9ca3af;")
        layout.addWidget(self._steps_label)

        sep1 = QLabel("·")
        sep1.setStyleSheet("color: #4b5563; font-size: 10px;")
        layout.addWidget(sep1)

        self._tokens_label = QLabel("Tokens: 0")
        self._tokens_label.setFont(font)
        self._tokens_label.setStyleSheet("color: #9ca3af;")
        layout.addWidget(self._tokens_label)

        sep2 = QLabel("·")
        sep2.setStyleSheet("color: #4b5563; font-size: 10px;")
        layout.addWidget(sep2)

        self._time_label = QLabel("0.0s")
        self._time_label.setFont(font)
        self._time_label.setStyleSheet("color: #9ca3af;")
        layout.addWidget(self._time_label)

        sep3 = QLabel("·")
        sep3.setStyleSheet("color: #4b5563; font-size: 10px;")
        layout.addWidget(sep3)

        self._retries_label = QLabel("Retries: 0")
        self._retries_label.setFont(font)
        self._retries_label.setStyleSheet("color: #9ca3af;")
        layout.addWidget(self._retries_label)

        sep4 = QLabel("·")
        sep4.setStyleSheet("color: #4b5563; font-size: 10px;")
        layout.addWidget(sep4)

        self._context_label = QLabel("Context: —")
        self._context_label.setFont(font)
        self._context_label.setStyleSheet("color: #9ca3af;")
        layout.addWidget(self._context_label)

        layout.addStretch()

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #22c55e; font-size: 8px;")
        layout.addWidget(self._status_dot)

    def start(self, max_steps: int | None = None) -> None:
        """Show the bar and start timing."""
        self._start_time = time.monotonic()
        self._steps = 0
        self._max_steps = max_steps
        self._tokens = 0
        self._retries = 0
        self._context_pct = 0
        self._update_labels()
        self.setVisible(True)
        self._timer.start()

    def stop(self) -> None:
        """Stop the bar (keeps visible with final values)."""
        self._timer.stop()

    def hide_bar(self) -> None:
        """Hide the bar completely."""
        self._timer.stop()
        self.setVisible(False)

    def update_steps(self, current: int, max_steps: int | None = None) -> None:
        self._steps = current
        # A plan-provided total replaces any previous one. Passing None
        # (the default) leaves the total untouched; start() resets it per
        # run so a stale budget total never leaks into the label.
        if max_steps is not None:
            self._max_steps = max_steps
        self._update_labels()

    def update_tokens(self, tokens: int) -> None:
        self._tokens = tokens
        self._update_labels()

    def update_retries(self, retries: int) -> None:
        self._retries = retries
        self._update_labels()

    def update_context(self, pct: float) -> None:
        self._context_pct = pct
        self._update_labels()

    def _update_time(self) -> None:
        self._update_labels()

    def _update_labels(self) -> None:
        elapsed = time.monotonic() - self._start_time if self._start_time else 0
        if self._max_steps is not None:
            self._steps_label.setText(f"Steps: {self._steps}/{self._max_steps}")
        else:
            self._steps_label.setText(f"Steps: {self._steps}")

        if self._tokens > 1000:
            self._tokens_label.setText(f"Tokens: {self._tokens / 1000:.1f}k")
        else:
            self._tokens_label.setText(f"Tokens: {self._tokens}")

        if elapsed < 60:
            self._time_label.setText(f"{elapsed:.1f}s")
        else:
            self._time_label.setText(f"{elapsed / 60:.1f}m")

        self._retries_label.setText(f"Retries: {self._retries}")

        if self._context_pct > 0:
            color = "#22c55e" if self._context_pct < 70 else "#f59e0b" if self._context_pct < 90 else "#ef4444"
            self._context_label.setText(f"Context: {self._context_pct:.0f}%")
            self._context_label.setStyleSheet(f"color: {color}; font-size: 10px;")
        else:
            self._context_label.setText("Context: —")
