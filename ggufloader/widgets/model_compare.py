"""
ModelCompare - Side-by-side model comparison widget.

Shows key metrics for two models:
- Architecture, quantization, parameter count
- Context length, layer count
- GPU support, memory usage
- Token generation speed
- Chat quality indicators

Pattern from: LMSys Chatbot Arena + HuggingFace model cards.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class ModelCard(QFrame):
    """Display info for a single model."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("modelCard")
        self.setFrameStyle(QFrame.StyledPanel)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self._name_label = QLabel("—")
        self._name_label.setObjectName("toolCardTitle")
        self._name_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        layout.addWidget(self._name_label)

        grid = QGridLayout()
        grid.setSpacing(4)

        self._rows: dict[str, tuple[QLabel, QLabel]] = {}
        fields = [
            ("architecture", "Architecture"),
            ("quantization", "Quantization"),
            ("parameters", "Parameters"),
            ("layers", "Layers"),
            ("context", "Context Length"),
            ("gpu", "GPU"),
            ("memory", "Memory"),
            ("speed", "Speed"),
            ("family", "Model Family"),
            ("format", "Format"),
        ]
        for i, (key, label_text) in enumerate(fields):
            label = QLabel(f"{label_text}:")
            label.setStyleSheet("color: #9ca3af; font-size: 10px;")
            value = QLabel("—")
            value.setStyleSheet("font-size: 10px; font-weight: bold;")
            grid.addWidget(label, i, 0)
            grid.addWidget(value, i, 1)
            self._rows[key] = (label, value)

        layout.addLayout(grid)

    def set_model(self, info: dict) -> None:
        """Update the card with model info."""
        name = info.get("name", "—")
        self._name_label.setText(f"📄 {name}")
        for key, (label, value) in self._rows.items():
            v = info.get(key, "—")
            if isinstance(v, (int, float)):
                value.setText(str(v))
            else:
                value.setText(str(v) if v else "—")

    def highlight_differences(self, other: ModelCard) -> None:
        """Highlight fields that differ between this card and another."""
        for key, (label, value) in self._rows.items():
            other_value = other._rows.get(key, (None, None))[1]
            if other_value is None:
                continue
            this_text = value.text()
            other_text = other_value.text()
            if this_text != other_text and this_text != "—" and other_text != "—":
                value.setStyleSheet("font-size: 10px; font-weight: bold; color: #60a5fa;")
                other_value.setStyleSheet("font-size: 10px; font-weight: bold; color: #f59e0b;")


class ModelCompare(QWidget):
    """Side-by-side model comparison view.

    Usage:
        compare = ModelCompare()
        compare.set_left({"name": "Mistral-7B", "layers": 32, ...})
        compare.set_right({"name": "Llama-3-8B", "layers": 32, ...})
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("modelCompare")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("📊 Model Comparison")
        title.setObjectName("panelTitle")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        header.addWidget(title)
        header.addStretch()

        self._compare_btn = QPushButton("🔍 Compare")
        self._compare_btn.setObjectName("primaryButton")
        self._compare_btn.clicked.connect(self._do_compare)
        header.addWidget(self._compare_btn)
        layout.addLayout(header)

        # Splitter with two cards
        self._splitter = QSplitter(Qt.Horizontal)
        self._left_card = ModelCard()
        self._right_card = ModelCard()
        self._splitter.addWidget(self._left_card)
        self._splitter.addWidget(self._right_card)
        self._splitter.setSizes([400, 400])
        layout.addWidget(self._splitter, 1)

        # Difference summary
        self._diff_label = QLabel("")
        self._diff_label.setObjectName("mutedLabel")
        self._diff_label.setWordWrap(True)
        layout.addWidget(self._diff_label)

    def set_left(self, info: dict) -> None:
        self._left_card.set_model(info)

    def set_right(self, info: dict) -> None:
        self._right_card.set_model(info)

    def set_models(self, left: dict, right: dict) -> None:
        self.set_left(left)
        self.set_right(right)

    def _do_compare(self) -> None:
        """Highlight differences between the two models."""
        self._left_card.highlight_differences(self._right_card)
        self._right_card.highlight_differences(self._left_card)

        # Build diff summary
        diffs = []
        for key in self._left_card._rows:
            left_val = self._left_card._rows[key][1].text()
            right_val = self._right_card._rows[key][1].text()
            if left_val != right_val and left_val != "—" and right_val != "—":
                label = self._left_card._rows[key][0].text().rstrip(":")
                diffs.append(f"{label}: {left_val} vs {right_val}")
        if diffs:
            self._diff_label.setText("Differences:\n" + "\n".join(f"  • {d}" for d in diffs))
        else:
            self._diff_label.setText("No differences found.")

    def clear(self) -> None:
        self._left_card.set_model({})
        self._right_card.set_model({})
        self._diff_label.setText("")
