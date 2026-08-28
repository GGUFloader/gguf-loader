"""
AgentHealthWidget - Compact health status display for the sidebar.

Pattern from: OpenHands status bar + DeepSeek health indicator.
A small collapsible widget showing:
- Overall health status (green/yellow/red)
- Memory usage
- Token budget usage
- Tool success rate
- Active features count
- Quick diagnostic button
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class HealthIndicator(QLabel):
    """A colored dot health indicator."""

    def __init__(self, parent=None):
        super().__init__("●", parent)
        self.setFixedSize(16, 16)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont(FONT_FAMILY, 10))
        self._state = "unknown"

    def set_state(self, state: str) -> None:
        """Set health state: 'healthy', 'degraded', 'unhealthy', 'unknown'."""
        self._state = state
        colors = {
            "healthy": "#22c55e",
            "degraded": "#f59e0b",
            "unhealthy": "#ef4444",
            "unknown": "#6b7280",
        }
        self.setStyleSheet(f"color: {colors.get(state, '#6b7280')}; font-size: 10px;")


class MetricRow(QWidget):
    """A compact metric display row."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._label = QLabel(label)
        self._label.setStyleSheet("color: #9ca3af; font-size: 10px;")
        layout.addWidget(self._label)

        self._value = QLabel("—")
        self._value.setStyleSheet("font-size: 10px; font-weight: bold;")
        layout.addWidget(self._value)

    def set_value(self, value: str, color: str = None) -> None:
        self._value.setText(value)
        if color:
            self._value.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {color};")


class AgentHealthWidget(QWidget):
    """Compact agent health display for the sidebar.

    Usage:
        widget = AgentHealthWidget()
        widget.update_health(health_data)
    """

    on_diagnose = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("agentHealthWidget")
        self._expanded = True
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with toggle
        header = QFrame()
        header.setFixedHeight(28)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 2, 12, 2)
        h_layout.setSpacing(6)

        self._indicator = HealthIndicator()
        h_layout.addWidget(self._indicator)

        title = QLabel("Agent Health")
        title.setStyleSheet("font-weight: bold; font-size: 11px;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self._toggle_btn = QPushButton("▼")
        self._toggle_btn.setFixedSize(16, 16)
        self._toggle_btn.setStyleSheet("border: none; font-size: 8px;")
        self._toggle_btn.clicked.connect(self._toggle_expand)
        h_layout.addWidget(self._toggle_btn)

        layout.addWidget(header)

        # Metrics container
        self._metrics_frame = QFrame()
        metrics_layout = QVBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(12, 4, 12, 4)
        metrics_layout.setSpacing(3)

        self._uptime_row = MetricRow("Uptime")
        self._tokens_row = MetricRow("Tokens")
        self._tools_row = MetricRow("Tools")
        self._features_row = MetricRow("Features")
        self._cache_row = MetricRow("Cache")

        metrics_layout.addWidget(self._uptime_row)
        metrics_layout.addWidget(self._tokens_row)
        metrics_layout.addWidget(self._tools_row)
        metrics_layout.addWidget(self._features_row)
        metrics_layout.addWidget(self._cache_row)

        # Diagnose button
        self._diag_btn = QPushButton("🔍 Run Diagnostics")
        self._diag_btn.setFixedHeight(24)
        self._diag_btn.setStyleSheet("font-size: 10px; padding: 2px;")
        self._diag_btn.clicked.connect(self.on_diagnose.emit)
        metrics_layout.addWidget(self._diag_btn)

        layout.addWidget(self._metrics_frame)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self._metrics_frame.setVisible(self._expanded)
        self._toggle_btn.setText("▼" if self._expanded else "▶")

    def update_health(self, health: dict) -> None:
        """Update the display with health data."""
        status = health.get("status", "unknown")
        self._indicator.set_state(status)

        # Uptime
        uptime = health.get("uptime_seconds", 0)
        if uptime < 60:
            self._uptime_row.set_value(f"{int(uptime)}s")
        elif uptime < 3600:
            self._uptime_row.set_value(f"{int(uptime / 60)}m")
        else:
            self._uptime_row.set_value(f"{int(uptime / 3600)}h")

        # Tokens
        tokens = health.get("total_tokens", 0)
        if tokens > 1000:
            self._tokens_row.set_value(f"{tokens / 1000:.1f}k")
        else:
            self._tokens_row.set_value(str(tokens))

        # Tools
        tools = health.get("tools_used", 0)
        success_rate = health.get("tool_success_rate", 0)
        tool_color = "#22c55e" if success_rate >= 90 else "#f59e0b" if success_rate >= 70 else "#ef4444"
        self._tools_row.set_value(f"{tools} ({success_rate:.0f}%)", tool_color)

        # Features
        features = health.get("features_enabled", 0)
        self._features_row.set_value(str(features))

        # Cache
        cache_hit = health.get("cache_hit_rate", 0)
        cache_color = "#22c55e" if cache_hit >= 50 else "#f59e0b" if cache_hit >= 20 else "#6b7280"
        self._cache_row.set_value(f"{cache_hit:.0f}%", cache_color)

    def set_status(self, status: str, message: str = "") -> None:
        """Set a simple status message."""
        self._indicator.set_state(status)
        if message:
            self._tokens_row.set_value(message)
