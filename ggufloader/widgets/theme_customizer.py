"""
ThemeCustomizer - Theme customization widget.

Allows users to:
- Pick an accent color from a palette
- Adjust font size
- Toggle compact mode
- Preview changes live

Pattern from: VS Code settings + Discord theme picker.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


# Preset accent colors
ACCENT_COLORS = [
    ("#e8a33d", "Amber (Default)"),
    ("#3b82f6", "Blue"),
    ("#8b5cf6", "Purple"),
    ("#ec4899", "Pink"),
    ("#22c55e", "Green"),
    ("#06b6d4", "Cyan"),
    ("#f97316", "Orange"),
    ("#ef4444", "Red"),
]


class ColorButton(QFrame):
    """A clickable color swatch."""

    color_selected = Signal(str)

    def __init__(self, color: str, name: str, parent=None):
        super().__init__(parent)
        self._color = color
        self._name = name
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(name)
        self.setStyleSheet(
            f"background: {color}; border-radius: 16px; border: 2px solid transparent;"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.color_selected.emit(self._color)
        self.setStyleSheet(
            f"background: {self._color}; border-radius: 16px; border: 2px solid #ffffff;"
        )

    def deselect(self) -> None:
        self.setStyleSheet(
            f"background: {self._color}; border-radius: 16px; border: 2px solid transparent;"
        )


class ThemeCustomizer(QWidget):
    """Theme customization panel.

    Usage:
        customizer = ThemeCustomizer()
        customizer.theme_changed.connect(on_theme_change)
    """

    theme_changed = Signal(dict)  # {"accent": "#xxx", "font_size": 14, "compact": False}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("themeCustomizer")
        self._current_accent = "#e8a33d"
        self._current_font_size = 14
        self._compact_mode = False
        self._color_buttons: list[ColorButton] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Accent color
        color_label = QLabel("Accent Color")
        color_label.setObjectName("sectionEyebrow")
        color_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        layout.addWidget(color_label)

        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        for color, name in ACCENT_COLORS:
            btn = ColorButton(color, name)
            btn.color_selected.connect(self._on_color_selected)
            self._color_buttons.append(btn)
            color_row.addWidget(btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        # Font size
        font_label = QLabel("Font Size")
        font_label.setObjectName("sectionEyebrow")
        font_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        layout.addWidget(font_label)

        font_row = QHBoxLayout()
        font_row.setSpacing(8)
        self._font_slider = QSlider(Qt.Horizontal)
        self._font_slider.setRange(10, 22)
        self._font_slider.setValue(14)
        self._font_slider.setTickPosition(QSlider.TicksBelow)
        self._font_slider.setTickInterval(2)
        self._font_slider.valueChanged.connect(self._on_font_changed)
        font_row.addWidget(self._font_slider, 1)

        self._font_value = QLabel("14px")
        self._font_value.setFixedWidth(40)
        self._font_value.setStyleSheet("font-size: 11px;")
        font_row.addWidget(self._font_value)
        layout.addLayout(font_row)

        # Compact mode
        compact_row = QHBoxLayout()
        compact_row.setSpacing(8)
        self._compact_btn = QPushButton("Compact Mode: OFF")
        self._compact_btn.setCheckable(True)
        self._compact_btn.setMinimumHeight(30)
        self._compact_btn.clicked.connect(self._on_compact_toggled)
        compact_row.addWidget(self._compact_btn)
        compact_row.addStretch()
        layout.addLayout(compact_row)

        # Preview
        preview_label = QLabel("Preview")
        preview_label.setObjectName("sectionEyebrow")
        preview_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        layout.addWidget(preview_label)

        self._preview = QFrame()
        self._preview.setFixedHeight(60)
        self._preview.setStyleSheet(
            f"background: #1f2937; border-radius: 8px; border: 2px solid {self._current_accent};"
        )
        preview_layout = QVBoxLayout(self._preview)
        preview_layout.setContentsMargins(12, 8, 12, 8)
        self._preview_text = QLabel("Sample text with accent color")
        self._preview_text.setStyleSheet(f"color: {self._current_accent}; font-size: 12px;")
        preview_layout.addWidget(self._preview_text)
        layout.addWidget(self._preview)

        layout.addStretch()

    def _on_color_selected(self, color: str) -> None:
        self._current_accent = color
        for btn in self._color_buttons:
            if btn._color != color:
                btn.deselect()
        self._update_preview()
        self._emit_change()

    def _on_font_changed(self, value: int) -> None:
        self._current_font_size = value
        self._font_value.setText(f"{value}px")
        self._emit_change()

    def _on_compact_toggled(self, checked: bool) -> None:
        self._compact_mode = checked
        self._compact_btn.setText(f"Compact Mode: {'ON' if checked else 'OFF'}")
        self._emit_change()

    def _update_preview(self) -> None:
        self._preview.setStyleSheet(
            f"background: #1f2937; border-radius: 8px; border: 2px solid {self._current_accent};"
        )
        self._preview_text.setStyleSheet(
            f"color: {self._current_accent}; font-size: {self._current_font_size}px;"
        )

    def _emit_change(self) -> None:
        self.theme_changed.emit({
            "accent": self._current_accent,
            "font_size": self._current_font_size,
            "compact": self._compact_mode,
        })

    def get_config(self) -> dict:
        return {
            "accent": self._current_accent,
            "font_size": self._current_font_size,
            "compact": self._compact_mode,
        }

    def set_config(self, config: dict) -> None:
        if "accent" in config:
            self._current_accent = config["accent"]
            for btn in self._color_buttons:
                if btn._color == config["accent"]:
                    btn.mousePressEvent(None)
                else:
                    btn.deselect()
        if "font_size" in config:
            self._font_slider.setValue(config["font_size"])
        if "compact" in config:
            self._compact_btn.setChecked(config["compact"])
            self._compact_btn.setText(f"Compact Mode: {'ON' if config['compact'] else 'OFF'}")
        self._update_preview()
