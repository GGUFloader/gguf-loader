"""
SettingsSidebar - Left-hand panel for model configuration.

Kept deliberately focused: model loading, GPU acceleration and context
length. App-level concerns (appearance, clear chat, feedback, addons)
live in the main window's menu bar, and dependency management lives
entirely in the launcher scripts (launch.sh / launch.bat).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from config import DEFAULT_CONTEXT_SIZES, FONT_FAMILY


class SettingsSidebar(QFrame):
    """Model settings sidebar that emits signals instead of reaching into the app."""

    load_model_requested = Signal()
    install_gpu_requested = Signal()
    gpu_toggled = Signal(bool)

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

        layout.addWidget(self._section_label("GPU Acceleration"))

        self.gpu_button = QPushButton("\U0001F680 GPU Acceleration: OFF")
        self.gpu_button.setObjectName("gpuToggle")
        self.gpu_button.setCheckable(True)
        self.gpu_button.setMinimumHeight(38)
        self.gpu_button.toggled.connect(self._update_gpu_label)
        self.gpu_button.toggled.connect(self.gpu_toggled.emit)
        layout.addWidget(self.gpu_button)

        self.install_gpu_btn = QPushButton("\u2B07 Install GPU Support")
        self.install_gpu_btn.setObjectName("gpuInstallBtn")
        self.install_gpu_btn.setMinimumHeight(38)
        self.install_gpu_btn.setToolTip(
            "Installs the GPU-enabled llama-cpp-python build "
            "(CUDA on Windows/Linux, Metal on macOS). The app restarts "
            "afterwards so the new build takes effect."
        )
        self.install_gpu_btn.clicked.connect(self.install_gpu_requested.emit)
        layout.addWidget(self.install_gpu_btn)

        self.gpu_install_status = QLabel("")
        self.gpu_install_status.setObjectName("mutedLabel")
        self.gpu_install_status.setWordWrap(True)
        layout.addWidget(self.gpu_install_status)

        layout.addWidget(self._section_label("Context Length"))

        self.context_combo = QComboBox()
        self.context_combo.addItems(DEFAULT_CONTEXT_SIZES)
        self.context_combo.setCurrentIndex(6)  # Default 32768
        self.context_combo.setMinimumHeight(35)
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

    def _update_gpu_label(self, enabled: bool) -> None:
        state = "ON" if enabled else "OFF"
        self.gpu_button.setText(f"\U0001F680 GPU Acceleration: {state}")

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
        return "GPU Accelerated" if self.gpu_button.isChecked() else "CPU Only"

    # ------------------------------------------------------------------
    # GPU install state (called by the main window)
    # ------------------------------------------------------------------
    def set_gpu_installed(self, installed: bool) -> None:
        """Reflect whether a GPU-enabled build is installed (green tick)."""
        if installed:
            self.install_gpu_btn.setText("\u2705 GPU Support Installed")
            self.install_gpu_btn.setToolTip(
                "GPU support is installed and will be used when GPU "
                "Acceleration is turned on."
            )
            self.install_gpu_btn.setProperty("state", "ok")
        else:
            self.install_gpu_btn.setText("\u2B07 Install GPU Support")
            self.install_gpu_btn.setToolTip(
                "Installs the GPU-enabled llama-cpp-python build "
                "(CUDA on Windows/Linux, Metal on macOS). The app restarts "
                "afterwards so the new build takes effect."
            )
            self.install_gpu_btn.setProperty("state", "")
        self.install_gpu_btn.style().unpolish(self.install_gpu_btn)
        self.install_gpu_btn.style().polish(self.install_gpu_btn)

    def set_gpu_install_busy(self, busy: bool) -> None:
        self.install_gpu_btn.setEnabled(not busy)
        self.gpu_install_status.setText("Installing GPU support…" if busy else "")

    def append_gpu_output(self, line: str) -> None:
        """Show the latest pip output line under the GPU buttons."""
        if len(line) > 72:
            line = line[:72] + "\u2026"
        self.gpu_install_status.setText(line)

    def get_context_size(self) -> int:
        try:
            return int(self.context_combo.currentText())
        except ValueError:
            return 32768
