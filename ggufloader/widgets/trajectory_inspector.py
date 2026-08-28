"""
TrajectoryInspector - Full execution trajectory viewer.

Shows the complete tool call history with timing, token costs,
risk assessment, and step-by-step replay. Pattern from
SWE-agent Inspector + DeepSeek TurnNavigator.

This is a dockable side panel that shows the full agent run
as a structured timeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class TrajectoryStep(QFrame):
    """A single step in the trajectory timeline."""

    step_clicked = Signal(int)  # step index

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setObjectName("trajectoryStep")
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Step number
        self._num = QLabel(str(index + 1))
        self._num.setFixedWidth(24)
        self._num.setAlignment(Qt.AlignCenter)
        self._num.setObjectName("trajectoryStepNum")
        layout.addWidget(self._num)

        # Status dot
        self._dot = QLabel("●")
        self._dot.setFixedWidth(12)
        self._dot.setAlignment(Qt.AlignCenter)
        self._dot.setStyleSheet("color: #6b7280; font-size: 8px;")
        layout.addWidget(self._dot)

        # Description
        self._desc = QLabel()
        self._desc.setObjectName("trajectoryStepDesc")
        self._desc.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._desc, 1)

        # Timing
        self._timing = QLabel()
        self._timing.setObjectName("trajectoryStepTiming")
        self._timing.setStyleSheet("color: #9ca3af; font-size: 10px;")
        self._timing.setFixedWidth(60)
        layout.addWidget(self._timing)

        # Risk badge
        self._risk = QLabel()
        self._risk.setFixedWidth(50)
        self._risk.setAlignment(Qt.AlignCenter)
        self._risk.setStyleSheet("font-size: 9px; border-radius: 3px;")
        layout.addWidget(self._risk)

    def set_status(self, status: str) -> """pending|running|success|error|denied""":
        colors = {
            "pending": "#6b7280",
            "running": "#3b82f6",
            "success": "#22c55e",
            "error": "#ef4444",
            "denied": "#f59e0b",
        }
        self._dot.setStyleSheet(f"color: {colors.get(status, '#6b7280')}; font-size: 8px;")

    def set_description(self, text: str) -> None:
        self._desc.setText(text)

    def set_timing(self, ms: int | None) -> None:
        if ms is not None:
            if ms < 1000:
                self._timing.setText(f"{ms}ms")
            else:
                self._timing.setText(f"{ms / 1000:.1f}s")
        else:
            self._timing.setText("—")

    def set_risk(self, level: str) -> None:
        colors = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444"}
        labels = {"low": "LOW", "medium": "MED", "high": "HIGH"}
        color = colors.get(level, "#6b7280")
        label = labels.get(level, level)
        self._risk.setText(label)
        self._risk.setStyleSheet(
            f"color: {color}; font-size: 9px; "
            f"background: {color}22; border-radius: 3px; padding: 1px 4px;"
        )


class TrajectoryDetail(QFrame):
    """Detail view for a selected trajectory step."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("trajectoryDetail")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self._title = QLabel("Select a step to view details")
        self._title.setObjectName("trajectoryDetailTitle")
        font = QFont(FONT_FAMILY, 12, QFont.Bold)
        self._title.setFont(font)
        layout.addWidget(self._title)

        self._tool_info = QLabel()
        self._tool_info.setWordWrap(True)
        self._tool_info.setStyleSheet("font-size: 11px; color: #9ca3af;")
        layout.addWidget(self._tool_info)

        self._content = QTextEdit()
        self._content.setReadOnly(True)
        self._content.setObjectName("trajectoryDetailContent")
        layout.addWidget(self._content, 1)

    def show_step(self, step_data: dict) -> None:
        tool = step_data.get("tool", "unknown")
        params = step_data.get("parameters", {})
        result = step_data.get("result", "")
        risk = step_data.get("risk", "low")
        timing_ms = step_data.get("timing_ms")

        self._title.setText(f"Step {step_data.get('index', '?')}: {tool}")

        info_parts = [f"Tool: {tool}"]
        if timing_ms is not None:
            info_parts.append(f"Time: {timing_ms}ms")
        info_parts.append(f"Risk: {risk.upper()}")
        if step_data.get("error"):
            info_parts.append(f"Error: {step_data['error']}")
        self._tool_info.setText(" · ".join(info_parts))

        # Build content
        lines = []
        if params:
            lines.append("=== Parameters ===")
            for k, v in params.items():
                lines.append(f"  {k}: {v}")
            lines.append("")
        if result:
            lines.append("=== Result ===")
            lines.append(str(result)[:2000])
        if step_data.get("error"):
            lines.append("")
            lines.append("=== Error ===")
            lines.append(str(step_data["error"]))

        self._content.setPlainText("\n".join(lines))


class TrajectoryInspector(QWidget):
    """Full trajectory viewer - timeline + detail split view.

    Pattern from SWE-agent Inspector + DeepSeek TurnNavigator.
    Shows the complete agent execution as a step-by-step timeline
    with timing, risk badges, and expandable details.
    """

    step_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("trajectoryInspector")
        self._steps: list[dict] = []
        self._step_widgets: list[TrajectoryStep] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("trajectoryHeader")
        header.setFixedHeight(36)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 4, 12, 4)
        title = QLabel("📋 Execution Timeline")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("color: #9ca3af; font-size: 10px;")
        h_layout.addWidget(self._stats_label)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("trajectoryClearBtn")
        clear_btn.setFixedHeight(24)
        clear_btn.clicked.connect(self.clear)
        h_layout.addWidget(clear_btn)

        layout.addWidget(header)

        # Split: timeline on top, detail on bottom
        splitter = QSplitter(Qt.Vertical)

        # Timeline scroll
        timeline_scroll = QScrollArea()
        timeline_scroll.setWidgetResizable(True)
        timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._timeline_container = QWidget()
        self._timeline_layout = QVBoxLayout(self._timeline_container)
        self._timeline_layout.setContentsMargins(0, 4, 0, 4)
        self._timeline_layout.setSpacing(2)
        self._timeline_layout.addStretch()
        timeline_scroll.setWidget(self._timeline_container)
        splitter.addWidget(timeline_scroll)

        # Detail view
        self._detail = TrajectoryDetail()
        splitter.addWidget(self._detail)

        splitter.setSizes([300, 200])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    def add_step(self, tool: str, parameters: dict = None,
                 risk: str = "low", status: str = "pending") -> int:
        """Add a new step to the timeline. Returns the step index."""
        index = len(self._steps)
        step_data = {
            "index": index,
            "tool": tool,
            "parameters": parameters or {},
            "risk": risk,
            "status": status,
            "result": None,
            "error": None,
            "timing_ms": None,
            "timestamp": datetime.now().isoformat(),
        }
        self._steps.append(step_data)

        widget = TrajectoryStep(index)
        widget.set_description(self._step_description(tool, parameters))
        widget.set_status(status)
        widget.set_risk(risk)
        widget.step_clicked.connect(self._on_step_clicked)
        self._step_widgets.append(widget)

        self._timeline_layout.insertWidget(self._timeline_layout.count() - 1, widget)
        self._update_stats()
        return index

    def update_step(self, index: int, status: str = None,
                    result: str = None, error: str = None,
                    timing_ms: int = None) -> None:
        """Update an existing step with results."""
        if index < 0 or index >= len(self._steps):
            return
        step = self._steps[index]
        if status is not None:
            step["status"] = status
            self._step_widgets[index].set_status(status)
        if result is not None:
            step["result"] = result
        if error is not None:
            step["error"] = error
        if timing_ms is not None:
            step["timing_ms"] = timing_ms
            self._step_widgets[index].set_timing(timing_ms)
        self._update_stats()

    def clear(self) -> None:
        """Clear all steps."""
        self._steps.clear()
        for w in self._step_widgets:
            w.setParent(None)
        self._step_widgets.clear()
        self._detail._content.clear()
        self._detail._title.setText("Select a step to view details")
        self._detail._tool_info.setText("")
        self._update_stats()

    def get_full_trajectory(self) -> list[dict]:
        """Return the full trajectory data for export."""
        return list(self._steps)

    def get_summary(self) -> dict:
        """Return a summary of the trajectory."""
        total = len(self._steps)
        successes = sum(1 for s in self._steps if s["status"] == "success")
        errors = sum(1 for s in self._steps if s["status"] == "error")
        denied = sum(1 for s in self._steps if s["status"] == "denied")
        total_ms = sum(s.get("timing_ms") or 0 for s in self._steps)
        high_risk = sum(1 for s in self._steps if s.get("risk") == "high")

        return {
            "total_steps": total,
            "successes": successes,
            "errors": errors,
            "denied": denied,
            "total_time_ms": total_ms,
            "high_risk_calls": high_risk,
        }

    def _on_step_clicked(self, index: int) -> None:
        if 0 <= index < len(self._steps):
            self._detail.show_step(self._steps[index])
            self.step_selected.emit(index)

    def _step_description(self, tool: str, parameters: dict | None) -> str:
        if not parameters:
            return tool
        if tool == "run_command":
            cmd = parameters.get("command", "")
            return f"$ {cmd[:60]}"
        if tool == "read_file":
            path = parameters.get("path", "")
            return f"Read {path}"
        if tool == "write_file":
            path = parameters.get("path", "")
            return f"Write {path}"
        if tool == "edit_file":
            path = parameters.get("path", "")
            return f"Edit {path}"
        if tool == "list_directory":
            path = parameters.get("path", ".")
            return f"List {path}"
        if tool == "search_files":
            pattern = parameters.get("pattern", "")
            return f"Search '{pattern}'"
        return f"{tool}({', '.join(str(v) for v in list(parameters.values())[:2])})"

    def _update_stats(self) -> None:
        s = self.get_summary()
        parts = [f"{s['total_steps']} steps"]
        if s["total_time_ms"] > 0:
            parts.append(f"{s['total_time_ms'] / 1000:.1f}s")
        if s["errors"] > 0:
            parts.append(f"❌ {s['errors']}")
        if s["denied"] > 0:
            parts.append(f"⛔ {s['denied']}")
        if s["high_risk_calls"] > 0:
            parts.append(f"🔴 {s['high_risk_calls']} high-risk")
        self._stats_label.setText(" · ".join(parts))
