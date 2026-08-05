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
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QVBoxLayout, QWidget,
)

from config import (
    DEFAULT_CONTEXT_SIZES, FONT_FAMILY, GPU_OPTIONS,
)


class SettingsSidebar(QFrame):
    """Model settings sidebar that emits signals instead of reaching into the app."""

    load_model_requested = Signal()
    processing_mode_changed = Signal(str)
    context_changed = Signal(str)
    check_environment_requested = Signal()
    install_dependencies_requested = Signal()
    bootstrap_venv_requested = Signal()
    restart_app_requested = Signal()
    launch_script_requested = Signal(str)

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

        # ---- environment launcher ----
        layout.addWidget(self._section_label("Environment"))

        self.env_summary = QLabel("Checking environment…")
        self.env_summary.setObjectName("mutedLabel")
        self.env_summary.setWordWrap(True)
        layout.addWidget(self.env_summary)

        self.env_status = QLabel("")
        self.env_status.setObjectName("envStatus")
        self.env_status.setWordWrap(True)
        layout.addWidget(self.env_status)

        self.env_missing = QLabel("")
        self.env_missing.setObjectName("envMissing")
        self.env_missing.setWordWrap(True)
        self.env_missing.setVisible(False)
        layout.addWidget(self.env_missing)

        self.env_install_btn = QPushButton("\u2B07 Install Missing Dependencies")
        self.env_install_btn.setMinimumHeight(35)
        self.env_install_btn.setVisible(False)
        self.env_install_btn.clicked.connect(self.install_dependencies_requested.emit)
        layout.addWidget(self.env_install_btn)

        self.env_bootstrap_btn = QPushButton("\u2699\uFE0F Create .venv & Restart")
        self.env_bootstrap_btn.setMinimumHeight(35)
        self.env_bootstrap_btn.setVisible(False)
        self.env_bootstrap_btn.clicked.connect(self.bootstrap_venv_requested.emit)
        layout.addWidget(self.env_bootstrap_btn)

        check_row = QHBoxLayout()
        check_row.setSpacing(8)
        self.env_progress = QProgressBar()
        self.env_progress.setVisible(False)
        check_row.addWidget(self.env_progress, 1)
        self.env_check_btn = QPushButton("\U0001F504 Check Again")
        self.env_check_btn.setMinimumHeight(30)
        self.env_check_btn.setMaximumWidth(120)
        self.env_check_btn.clicked.connect(self.check_environment_requested.emit)
        check_row.addWidget(self.env_check_btn)
        layout.addLayout(check_row)

        # ---- launcher (scripts/ utilities) ----
        layout.addWidget(self._section_label("Launcher"))

        self.restart_btn = QPushButton("\U0001F504 Restart App")
        self.restart_btn.setMinimumHeight(32)
        self.restart_btn.clicked.connect(self.restart_app_requested.emit)
        layout.addWidget(self.restart_btn)

        from services.launcher_service import available_scripts
        grid = QGridLayout()
        grid.setSpacing(8)
        for index, (key, label) in enumerate(available_scripts()):
            button = QPushButton(label)
            button.setMinimumHeight(32)
            button.clicked.connect(
                lambda _checked, k=key: self.launch_script_requested.emit(k)
            )
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)

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

    # ------------------------------------------------------------------
    # Environment launcher (called by the main window)
    # ------------------------------------------------------------------
    def set_environment(self, env: dict) -> None:
        """Render the venv/dependency status returned by EnvironmentService.check()."""
        venv_tag = ".venv" if env.get("is_venv") else "system interpreter"
        self.env_summary.setText(
            f"Python {env.get('python_version', '?')} \u00B7 {venv_tag}"
        )

        missing = env.get("missing", [])
        if not env.get("is_venv"):
            self.env_status.setText("\u26A0 Not running from .venv")
            self._set_env_state("warn")
            self.env_bootstrap_btn.setVisible(True)
            self.env_install_btn.setVisible(False)
            self.env_missing.setVisible(False)
        elif missing:
            self.env_status.setText(
                f"\u25CF {len(missing)}/{env.get('total', 0)} dependencies missing"
            )
            self._set_env_state("err")
            self.env_missing.setText("Missing: " + ", ".join(missing))
            self.env_missing.setVisible(True)
            self.env_install_btn.setVisible(True)
            self.env_bootstrap_btn.setVisible(False)
        else:
            self.env_status.setText("\u2705 All dependencies installed")
            self._set_env_state("ok")
            self.env_missing.setVisible(False)
            self.env_install_btn.setVisible(False)
            self.env_bootstrap_btn.setVisible(False)

    def set_env_busy(self, busy: bool) -> None:
        """Disable the launcher controls while pip is running."""
        for button in (self.env_install_btn, self.env_bootstrap_btn, self.env_check_btn):
            button.setEnabled(not busy)
        self.env_progress.setVisible(busy)
        if busy:
            self.env_progress.setRange(0, 0)  # indeterminate

    def append_env_output(self, line: str) -> None:
        """Show the latest pip output line in the status label."""
        if len(line) > 72:
            line = line[:72] + "\u2026"
        self.env_status.setText(line)
        self._set_env_state("")

    def _set_env_state(self, state: str) -> None:
        self.env_status.setProperty("state", state)
        self.env_status.style().unpolish(self.env_status)
        self.env_status.style().polish(self.env_status)
