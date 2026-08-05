"""
SettingsSidebar - Left-hand settings panel (model, processing, appearance).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QSlider, QVBoxLayout, QWidget,
)

from config import (
    BUBBLE_FONT_SIZE, DEFAULT_CONTEXT_SIZES, FONT_FAMILY, GPU_OPTIONS,
)


class SettingsSidebar(QFrame):
    """Settings sidebar that emits signals instead of reaching into the app."""

    load_model_requested = Signal()
    processing_mode_changed = Signal(str)
    context_changed = Signal(str)
    dark_mode_toggled = Signal(bool)
    text_size_changed = Signal(int)
    clear_chat_requested = Signal()
    feedback_requested = Signal()

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
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("🤖 AI Chat Settings")
        title.setFont(QFont(FONT_FAMILY, 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addWidget(self._section_label("📁 Model Configuration"))

        self.load_model_btn = QPushButton("Select GGUF Model")
        self.load_model_btn.setMinimumHeight(40)
        self.load_model_btn.clicked.connect(self.load_model_requested.emit)
        layout.addWidget(self.load_model_btn)

        self.model_info = QLabel("No model loaded")
        self.model_info.setWordWrap(True)
        self.model_info.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.model_info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.model_info)

        layout.addWidget(self._section_label("⚡ Processing Mode"))

        self.processing_combo = QComboBox()
        self.processing_combo.addItems(GPU_OPTIONS)
        self.processing_combo.setCurrentIndex(0)
        self.processing_combo.setMinimumHeight(35)
        self.processing_combo.currentTextChanged.connect(self.processing_mode_changed.emit)
        layout.addWidget(self.processing_combo)

        layout.addWidget(self._section_label("📏 Context Length"))

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
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        layout.addWidget(self.status_label)

        layout.addWidget(self._section_label("🎨 Appearance"))

        self.dark_mode_cb = QCheckBox("🌙 Dark Mode")
        self.dark_mode_cb.setMinimumHeight(30)
        self.dark_mode_cb.toggled.connect(self.dark_mode_toggled.emit)
        layout.addWidget(self.dark_mode_cb)

        size_row = QWidget()
        size_layout = QHBoxLayout(size_row)
        size_layout.setContentsMargins(0, 5, 0, 5)
        size_layout.setSpacing(10)

        small = QLabel("A")
        small.setFont(QFont(FONT_FAMILY, 10))
        small.setStyleSheet("color: #666;")
        size_layout.addWidget(small)

        self.text_size_slider = QSlider(Qt.Horizontal)
        self.text_size_slider.setMinimum(10)
        self.text_size_slider.setMaximum(24)
        self.text_size_slider.setValue(14)
        self.text_size_slider.setTickPosition(QSlider.TicksBelow)
        self.text_size_slider.setTickInterval(2)
        self.text_size_slider.valueChanged.connect(self._on_text_size_changed)
        size_layout.addWidget(self.text_size_slider)

        large = QLabel("A")
        large.setFont(QFont(FONT_FAMILY, 16, QFont.Bold))
        size_layout.addWidget(large)

        self.font_size_display = QLabel("14")
        self.font_size_display.setAlignment(Qt.AlignCenter)
        self.font_size_display.setMinimumWidth(25)
        self.font_size_display.setStyleSheet(
            "QLabel { background-color: #f0f0f0; border: 1px solid #ccc;"
            " border-radius: 3px; padding: 2px 4px; color: #333; }"
        )
        size_layout.addWidget(self.font_size_display)

        layout.addWidget(size_row)

        self.clear_chat_btn = QPushButton("🗑️ Clear Chat")
        self.clear_chat_btn.setMinimumHeight(35)
        self.clear_chat_btn.clicked.connect(self.clear_chat_requested.emit)
        layout.addWidget(self.clear_chat_btn)

        self.feedback_btn = QPushButton("📧 Send Feedback")
        self.feedback_btn.setMinimumHeight(35)
        self.feedback_btn.clicked.connect(self.feedback_requested.emit)
        layout.addWidget(self.feedback_btn)

        layout.addStretch()

        about = QLabel("ℹ️ Developed by Hussain Nazary\nGithub ID: @hussainnazary2")
        about.setWordWrap(True)
        about.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(about)

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
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

    def set_text_size(self, size: int) -> None:
        self.text_size_slider.setValue(size)

    def get_processing_mode(self) -> str:
        return self.processing_combo.currentText()

    def get_context_size(self) -> int:
        try:
            return int(self.context_combo.currentText())
        except ValueError:
            return 32768

    def _on_text_size_changed(self, value: int) -> None:
        self.font_size_display.setText(str(value))
        self.text_size_changed.emit(value)
