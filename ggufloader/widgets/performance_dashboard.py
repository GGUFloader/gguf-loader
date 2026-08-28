"""
PerformanceDashboard - Real-time agent metrics display.

Shows:
- Token flow (tokens used/remaining per step)
- Step timing (ms per step, total time)
- Retry statistics (retries, circuit breaker state)
- Context budget (usage %, compactions)
- Memory store stats (memories stored, categories)
- Tool execution stats (success/fail, avg time)

Pattern from: DeepSeek StatsLine + Aider cost display.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class MetricCard(QFrame):
    """A single metric display card."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setFixedHeight(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        self._label = QLabel(label)
        self._label.setStyleSheet("color: #9ca3af; font-size: 10px;")
        layout.addWidget(self._label)

        self._value = QLabel("—")
        self._value.setObjectName("metricValue")
        font = QFont(FONT_FAMILY, 16, QFont.Bold)
        self._value.setFont(font)
        layout.addWidget(self._value)

        self._sub = QLabel("")
        self._sub.setStyleSheet("color: #6b7280; font-size: 9px;")
        layout.addWidget(self._sub)

    def set_value(self, value: str, sub: str = "") -> None:
        self._value.setText(value)
        self._sub.setText(sub)

    def set_color(self, color: str) -> None:
        self._value.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")


class PerformanceDashboard(QWidget):
    """Real-time performance metrics for the agent.

    Displays a grid of metric cards showing:
    - Steps completed / total
    - Tokens used
    - Total time
    - Retry count
    - Context usage %
    - Tool success rate
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("performanceDashboard")
        self._start_time: float = 0
        self._step_times: list[float] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        title = QLabel("📊 Performance")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        header.addWidget(title)
        header.addStretch()
        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setFixedSize(24, 24)
        self._refresh_btn.setToolTip("Refresh metrics")
        header.addWidget(self._refresh_btn)
        layout.addLayout(header)

        # Metric grid
        grid = QGridLayout()
        grid.setSpacing(6)

        self._steps_card = MetricCard("Steps")
        self._tokens_card = MetricCard("Tokens")
        self._time_card = MetricCard("Time")
        self._retries_card = MetricCard("Retries")
        self._context_card = MetricCard("Context")
        self._tools_card = MetricCard("Tools")

        grid.addWidget(self._steps_card, 0, 0)
        grid.addWidget(self._tokens_card, 0, 1)
        grid.addWidget(self._time_card, 0, 2)
        grid.addWidget(self._retries_card, 1, 0)
        grid.addWidget(self._context_card, 1, 1)
        grid.addWidget(self._tools_card, 1, 2)

        layout.addLayout(grid)
        layout.addStretch()

    def reset(self) -> None:
        """Reset all metrics for a new session."""
        import time as _time
        self._start_time = _time.monotonic()
        self._step_times.clear()
        self._steps_card.set_value("0")
        self._tokens_card.set_value("0")
        self._time_card.set_value("0ms")
        self._retries_card.set_value("0")
        self._context_card.set_value("—")
        self._tools_card.set_value("—")

    def update_steps(self, current: int, total: int) -> None:
        self._steps_card.set_value(f"{current}/{total}")

    def update_tokens(self, used: int, remaining: int = 0) -> None:
        if used > 1000:
            display = f"{used / 1000:.1f}k"
        else:
            display = str(used)
        sub = f"{remaining} remaining" if remaining else ""
        self._tokens_card.set_value(display, sub)

    def update_time(self, elapsed_ms: int) -> None:
        if elapsed_ms < 1000:
            self._time_card.set_value(f"{elapsed_ms}ms")
        else:
            self._time_card.set_value(f"{elapsed_ms / 1000:.1f}s")

    def update_retries(self, retries: int, circuit_state: str = "closed") -> None:
        color = "#22c55e" if circuit_state == "closed" else "#ef4444"
        self._retries_card.set_value(str(retries))
        self._retries_card.set_color(color)

    def update_context(self, used: int, total: int) -> None:
        if total <= 0:
            self._context_card.set_value("—")
            return
        pct = round(used / total * 100, 1)
        color = "#22c55e" if pct < 70 else "#f59e0b" if pct < 90 else "#ef4444"
        self._context_card.set_value(f"{pct}%", f"{used}/{total}")
        self._context_card.set_color(color)

    def update_tools(self, success: int, failed: int) -> None:
        total = success + failed
        if total == 0:
            self._tools_card.set_value("—")
            return
        rate = round(success / total * 100)
        color = "#22c55e" if rate >= 90 else "#f59e0b" if rate >= 70 else "#ef4444"
        self._tools_card.set_value(f"{rate}%", f"{success}/{total} succeeded")
        self._tools_card.set_color(color)

    def record_step_time(self, ms: float) -> None:
        """Record timing for a single step."""
        self._step_times.append(ms)
        total = sum(self._step_times)
        self.update_time(int(total))
