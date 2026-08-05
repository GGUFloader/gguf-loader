"""
SettingsSidebar - Left-hand panel for model configuration.

Kept deliberately focused: model loading, processing mode and context
length. App-level concerns (appearance, clear chat, feedback, addons)
live in the main window's menu bar.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from config import (
    DEFAULT_CONTEXT_SIZES, FONT_FAMILY, GPU_OPTIONS,
)


class SettingsSidebar(QFrame):
    """Model settings sidebar that emits signals instead of reaching into the app."""

    load_model_requested = Signal()
    processing_mode_changed = Signal(str)
    context_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)
        self.setFrameStyle(QFrame.StyledPanel)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("\u2699\uFE0F Model Settings")
        title.setObjectName("panelTitle")
        title.setAlignment(Qt.AlignLeft)
        layout.addWidget(title)
        layout.addSpacing(4)

        layout.addWidget(self._section_label("Model"))

        self.load_model_btn = QPushButton("Load GGUF Model")
        self.load_model_btn.setObjectName("primaryButton")
        self.load_model_btn.setMinimumHeight(40)
        self.load_model_btn.clicked.connect(self.load_model_requested.emit)
        layout.addWidget(self.load_model_btn)

        self.model_info = QLabel("No model loaded")
        self.model_info.setObjectName("mutedLabel")
        self.model_info.setWordWrap(True)
        self.model_info.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        layout.addWidget(self.model_info)

        layout.addWidget(self._section_label("Processing"))

        self.processing_combo = QComboBox()
        self.processing_combo.addItems(GPU_OPTIONS)
        self.processing_combo.setCurrentIndex(0)
        self.processing_combo.setMinimumHeight(35)
        self.processing_combo.currentTextChanged.connect(self.processing_mode_changed.emit)
        layout.addWidget(self.processing_combo)

        layout.addWidget(self._section_label("Context Length"))

        self.context_combo = QComboBox()
        self.context_combo.addItems(DEFAULT_CONTEXT_SIZES)
        self.context_combo.setCurrentIndex(6)  # Default 32768
        self.context_combo.setMinimumHeight(35)
        self.context_combo.currentTextChanged.connect(self.context_changed.emit)
        layout.addWidget(self.context_combo)

        # Progress + status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to load model")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _section_label(self, text: str) -> QLabel:
        """Tiny uppercase eyebrow label; the accent color comes from QSS."""
        label = QLabel(text.upper())
        label.setObjectName("sectionEyebrow")
        label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        return label

    # ------------------------------------------------------------------
    # State setters (called by the main window)
    # ------------------------------------------------------------------
    def set_loading(self, visible: bool) -> None:
        self.load_model_btn.setEnabled(not visible)
        self.progress_bar.setVisible(visible)
        if visible:
            self.progress_bar.setRange(0, 0)  # indeterminate

    def set_model_info(self, text: str) -> None:
        self.model_info.setText(text)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        # Color the status by its emoji marker (QSS selects on the property).
        if "✅" in text or "🟢" in text:
            state = "ok"
        elif "❌" in text or "🔴" in text:
            state = "err"
        else:
            state = ""
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def get_processing_mode(self) -> str:
        return self.processing_combo.currentText()

    def get_context_size(self) -> int:
        try:
            return int(self.context_combo.currentText())
        except ValueError:
            return 32768
