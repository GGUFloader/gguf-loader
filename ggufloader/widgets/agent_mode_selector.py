"""
AgentModeSelector - Visual preset picker for agent modes.

Pattern from: OpenHands agent type selector + Aider's edit-format picker.
A dropdown/card selector that shows all available agent presets
with icons, descriptions, and key settings.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class PresetCard(QFrame):
    """A single preset selection card."""

    selected = Signal(str)  # preset_id

    def __init__(self, preset_id: str, icon: str, name: str,
                 description: str, active: bool = False, parent=None):
        super().__init__(parent)
        self.preset_id = preset_id
        self._active = active
        self.setObjectName("presetCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(60)

        if active:
            self.setProperty("active", True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(QFont(FONT_FAMILY, 20))
        icon_label.setFixedWidth(36)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        text_layout.addWidget(name_label)
        desc_label = QLabel(description[:70])
        desc_label.setStyleSheet("color: #9ca3af; font-size: 10px;")
        text_layout.addWidget(desc_label)
        layout.addLayout(text_layout, 1)

        # Active indicator
        self._indicator = QLabel("✓" if active else "")
        self._indicator.setFixedWidth(20)
        self._indicator.setAlignment(Qt.AlignCenter)
        self._indicator.setStyleSheet("font-size: 14px; color: #22c55e;")
        layout.addWidget(self._indicator)

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.preset_id)
        super().mousePressEvent(event)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._indicator.setText("✓" if active else "")
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class AgentModeSelector(QWidget):
    """Visual agent mode selector with preset cards.

    Usage:
        selector = AgentModeSelector()
        selector.set_presets(preset_list)
        selector.on_mode_selected.connect(handler)
    """

    on_mode_selected = Signal(str)  # preset_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("agentModeSelector")
        self._cards: dict[str, PresetCard] = {}
        self._active_id: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(36)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 4, 12, 4)
        title = QLabel("🎯 Agent Mode")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        self._current_label = QLabel("Full Stack")
        self._current_label.setStyleSheet("color: #9ca3af; font-size: 10px;")
        h_layout.addWidget(self._current_label)
        layout.addWidget(header)

        # Scrollable card list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(200)

        container = QWidget()
        self._card_layout = QVBoxLayout(container)
        self._card_layout.setSpacing(4)
        self._card_layout.setContentsMargins(8, 4, 8, 4)
        self._card_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def set_presets(self, presets: list[dict]) -> None:
        """Set available presets.

        Each dict: {id, name, description, icon}
        """
        for card in self._cards.values():
            card.setParent(None)
        self._cards.clear()

        for preset in presets:
            card = PresetCard(
                preset_id=preset.get("id", ""),
                icon=preset.get("icon", "🔧"),
                name=preset.get("name", ""),
                description=preset.get("description", ""),
            )
            card.selected.connect(self._on_card_selected)
            self._cards[preset.get("id", "")] = card
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

    def set_active(self, preset_id: str) -> None:
        """Set the active preset."""
        self._active_id = preset_id
        for pid, card in self._cards.items():
            card.set_active(pid == preset_id)
        # Update header label
        card = self._cards.get(preset_id)
        if card:
            self._current_label.setText(card.findChild(QLabel).text() if card.findChild(QLabel) else preset_id)

    def _on_card_selected(self, preset_id: str) -> None:
        self.set_active(preset_id)
        self.on_mode_selected.emit(preset_id)
