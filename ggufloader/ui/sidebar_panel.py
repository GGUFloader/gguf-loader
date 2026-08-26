"""
SettingsSidebar - Left-hand panel for model configuration.

Kept deliberately focused: model loading, GPU acceleration and context
length. App-level concerns (appearance, clear chat, feedback, addons)
live in the main window's menu bar, and dependency management lives
entirely in the launcher scripts (launch.sh / launch.bat).
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QLabel, QListWidget, QListWidgetItem, QMenu,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from ggufloader.config import DEFAULT_CONTEXT_SIZES, FONT_FAMILY


class SettingsSidebar(QFrame):
    """Model settings sidebar that emits signals instead of reaching into the app."""

    load_model_requested = Signal()
    install_gpu_requested = Signal()
    gpu_toggled = Signal(bool)
    new_chat_requested = Signal()
    session_selected = Signal(str)
    session_rename_requested = Signal(str)
    session_delete_requested = Signal(str)

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

        # ---- Chats section ----
        layout.addWidget(self._section_label("Chats"))

        self.new_chat_btn = QPushButton("\u2795 New Chat")
        self.new_chat_btn.setObjectName("primaryButton")
        self.new_chat_btn.setMinimumHeight(38)
        self.new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self.new_chat_btn)

        self.session_list = QListWidget()
        self.session_list.setObjectName("sessionList")
        self.session_list.setMinimumHeight(140)
        self.session_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.session_list.customContextMenuRequested.connect(self._show_session_menu)
        self.session_list.itemClicked.connect(self._on_session_clicked)
        layout.addWidget(self.session_list, 1)

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

    # ------------------------------------------------------------------
    # Chat sessions (called by the main window)
    # ------------------------------------------------------------------
    def set_sessions(self, sessions: list[dict], active_id: str | None = None) -> None:
        """Re-render the session list; *sessions* comes from SessionStore."""
        self.session_list.blockSignals(True)
        self.session_list.clear()
        for meta in sessions:
            if meta.get("corrupt"):
                label = f"\u26a0 {meta['id']}"
                item = QListWidgetItem(label)
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                tooltip = f"Corrupt session file: {meta.get('error', '')}"
            else:
                title = meta.get("title") or "New Chat"
                badge = " \U0001F916" if meta.get("mode") == "agent" else ""
                label = f"{title}{badge}\n{self._relative_time(meta.get('updated', ''))}"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, meta["id"])
                if meta["id"] == active_id:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    self.session_list.setCurrentItem(item)
            item.setToolTip(tooltip if meta.get("corrupt") else (meta.get("title") or "New Chat"))
            self.session_list.addItem(item)
        self.session_list.blockSignals(False)

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.UserRole)
        if session_id:
            self.session_selected.emit(session_id)

    def _show_session_menu(self, pos) -> None:
        item = self.session_list.itemAt(pos)
        if item is None or not item.data(Qt.UserRole):
            return
        session_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        # Popup windows clear to black on Windows unless themed explicitly.
        from ggufloader.widgets.chat_bubble import _styled_text_menu
        _styled_text_menu(menu, self)
        rename_action = menu.addAction("Rename\u2026")
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(self.session_list.mapToGlobal(pos))
        if chosen is rename_action:
            self.session_rename_requested.emit(session_id)
        elif chosen is delete_action:
            self.session_delete_requested.emit(session_id)

    @staticmethod
    def _relative_time(iso_stamp: str) -> str:
        try:
            then = datetime.fromisoformat(iso_stamp)
        except (TypeError, ValueError):
            return ""
        seconds = max(0, int((datetime.now() - then).total_seconds()))
        if seconds < 60:
            return "now"
        if seconds < 3600:
            return f"{seconds // 60}m"
        if seconds < 86400:
            return f"{seconds // 3600}h"
        if seconds < 7 * 86400:
            return f"{seconds // 86400}d"
        return then.strftime("%b %d")
