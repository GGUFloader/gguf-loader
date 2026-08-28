"""
ModelPopover - Quick model info on hover.

A lightweight popup that appears when hovering over the model chip
in the header. Shows key model details without opening a full dialog.

Pattern from: VS Code hover tooltips + GitHub hover cards.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class ModelPopover(QFrame):
    """Hover popover showing model details.

    Usage:
        popover = ModelPopover(parent_widget)
        popover.set_model_info({"name": "Mistral-7B", "arch": "llama", ...})
        # Show on hover, hide on leave
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("modelPopover")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(500)
        self._hide_timer.timeout.connect(self.hide)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        self._name_label = QLabel("")
        self._name_label.setObjectName("toolCardTitle")
        self._name_label.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        layout.addWidget(self._name_label)

        grid = QGridLayout()
        grid.setSpacing(3)

        self._rows: dict[str, tuple[QLabel, QLabel]] = {}
        fields = [
            ("arch", "Architecture"),
            ("quant", "Quantization"),
            ("params", "Parameters"),
            ("layers", "Layers"),
            ("ctx", "Context"),
            ("gpu", "GPU"),
            ("vram", "VRAM"),
            ("family", "Family"),
        ]
        for i, (key, label_text) in enumerate(fields):
            lbl = QLabel(f"{label_text}:")
            lbl.setStyleSheet("color: #9ca3af; font-size: 9px;")
            val = QLabel("—")
            val.setStyleSheet("font-size: 9px; font-weight: bold;")
            grid.addWidget(lbl, i, 0)
            grid.addWidget(val, i, 1)
            self._rows[key] = (lbl, val)

        layout.addLayout(grid)

        self.setStyleSheet("""
            QFrame#modelPopover {
                background: #1f2937;
                border: 1px solid #4b5563;
                border-radius: 8px;
            }
        """)

    def set_model_info(self, info: dict) -> None:
        """Update the popover with model info."""
        name = info.get("name", "Unknown Model")
        self._name_label.setText(f"📄 {name}")
        for key, (lbl, val) in self._rows.items():
            v = info.get(key, "—")
            val.setText(str(v) if v else "—")

    def show_at(self, x: int, y: int) -> None:
        """Show the popover at the given screen coordinates."""
        self.move(x, y)
        self.show()
        self.raise_()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hide_timer.stop()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hide_timer.start()
