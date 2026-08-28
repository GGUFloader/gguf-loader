"""
FeatureDashboard - Show all agent capabilities and their status.

Pattern from: OpenHands plugin manager + DeepSeek settings panel.
A comprehensive dashboard showing:
- All 30+ agent capabilities and their status
- Quick-toggle switches
- Performance metrics per capability
- System health overview
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class CapabilityCard(QFrame):
    """A single capability display card."""

    toggled = Signal(str, bool)  # capability_name, enabled

    def __init__(self, name: str, description: str, enabled: bool = True,
                 parent=None):
        super().__init__(parent)
        self.name = name
        self.setObjectName("capabilityCard")
        self.setFixedHeight(50)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Status dot
        self._dot = QLabel("●")
        self._dot.setFixedWidth(12)
        self._dot.setAlignment(Qt.AlignCenter)
        self._update_dot(enabled)
        layout.addWidget(self._dot)

        # Name and description
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        self._name = QLabel(name.replace("_", " ").title())
        self._name.setStyleSheet("font-weight: bold; font-size: 11px;")
        text_layout.addWidget(self._name)
        self._desc = QLabel(description[:60])
        self._desc.setStyleSheet("color: #9ca3af; font-size: 9px;")
        text_layout.addWidget(self._desc)
        layout.addLayout(text_layout, 1)

        # Toggle button
        self._toggle = QPushButton("ON" if enabled else "OFF")
        self._toggle.setFixedSize(40, 22)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(enabled)
        self._toggle.setStyleSheet(
            "QPushButton { border-radius: 11px; font-size: 9px; font-weight: bold; }"
            "QPushButton:checked { background: #22c55e; color: white; }"
            "QPushButton:unchecked { background: #6b7280; color: white; }"
        )
        self._toggle.clicked.connect(lambda: self.toggled.emit(self.name, self._toggle.isChecked()))
        layout.addWidget(self._toggle)

    def set_enabled(self, enabled: bool) -> None:
        self._toggle.setChecked(enabled)
        self._toggle.setText("ON" if enabled else "OFF")
        self._update_dot(enabled)

    def _update_dot(self, enabled: bool) -> None:
        color = "#22c55e" if enabled else "#6b7280"
        self._dot.setStyleSheet(f"color: {color}; font-size: 10px;")


class FeatureDashboard(QWidget):
    """Comprehensive agent feature dashboard.

    Shows all capabilities with toggle controls and metrics.

    Usage:
        dashboard = FeatureDashboard()
        dashboard.set_capabilities(cap_list)
        dashboard.on_capability_toggled.connect(handler)
    """

    on_capability_toggled = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("featureDashboard")
        self._cards: dict[str, CapabilityCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("dashboardHeader")
        header.setFixedHeight(40)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 4, 12, 4)
        title = QLabel("⚙️ Agent Features")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self._status_label = QLabel("0/0 enabled")
        self._status_label.setStyleSheet("color: #9ca3af; font-size: 10px;")
        h_layout.addWidget(self._status_label)

        # Enable All / Disable All buttons
        enable_all = QPushButton("All On")
        enable_all.setFixedHeight(22)
        enable_all.setStyleSheet("font-size: 9px; padding: 2px 8px;")
        enable_all.clicked.connect(self._enable_all)
        h_layout.addWidget(enable_all)

        disable_all = QPushButton("All Off")
        disable_all.setFixedHeight(22)
        disable_all.setStyleSheet("font-size: 9px; padding: 2px 8px;")
        disable_all.clicked.connect(self._disable_all)
        h_layout.addWidget(disable_all)

        layout.addWidget(header)

        # Scrollable capability list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self._grid = QGridLayout(container)
        self._grid.setSpacing(4)
        self._grid.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    def set_capabilities(self, capabilities: list[dict]) -> None:
        """Set the list of capabilities to display.

        Each dict should have: name, description, status
        """
        # Clear existing
        for card in self._cards.values():
            card.setParent(None)
        self._cards.clear()

        # Add new cards in grid
        cols = 2
        for i, cap in enumerate(capabilities):
            name = cap.get("name", "")
            desc = cap.get("description", "")
            enabled = cap.get("status", "enabled") == "enabled"

            card = CapabilityCard(name, desc, enabled)
            card.toggled.connect(self._on_toggled)
            self._cards[name] = card

            row = i // cols
            col = i % cols
            self._grid.addWidget(card, row, col)

        self._update_status()

    def _on_toggled(self, name: str, enabled: bool) -> None:
        self._update_status()
        self.on_capability_toggled.emit(name, enabled)

    def _enable_all(self) -> None:
        for card in self._cards.values():
            card.set_enabled(True)
        self._update_status()
        for name in self._cards:
            self.on_capability_toggled.emit(name, True)

    def _disable_all(self) -> None:
        for card in self._cards.values():
            card.set_enabled(False)
        self._update_status()
        for name in self._cards:
            self.on_capability_toggled.emit(name, False)

    def _update_status(self) -> None:
        total = len(self._cards)
        enabled = sum(1 for c in self._cards.values() if c._toggle.isChecked())
        self._status_label.setText(f"{enabled}/{total} enabled")

    def get_enabled(self) -> list[str]:
        return [name for name, card in self._cards.items() if card._toggle.isChecked()]
