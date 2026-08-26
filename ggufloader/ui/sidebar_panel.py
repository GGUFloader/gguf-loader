"""
SettingsSidebar - Left-hand panel for model configuration.

Kept deliberately focused: model loading, GPU acceleration and context
length. App-level concerns (appearance, clear chat, feedback, addons)
live in the main window's menu bar, and dependency management lives
entirely in the launcher scripts (launch.sh / launch.bat).
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMenu, QProgressBar, QPushButton, QVBoxLayout, QWidget,
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
    params_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)
        self.setFrameStyle(QFrame.StyledPanel)
        self._pending_delete_id: str | None = None
        self._pending_delete_timer = QTimer(self)
        self._pending_delete_timer.setSingleShot(True)
        self._pending_delete_timer.setInterval(3000)
        self._pending_delete_timer.timeout.connect(self._cancel_pending_delete)
        self._last_sessions: list[dict] = []
        self._last_active_id: str | None = None
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

        # B2: GPU layers control (how many transformer blocks offloaded)
        gpu_layers_row = QHBoxLayout()
        gpu_layers_row.addWidget(QLabel("GPU Layers:"))
        from PySide6.QtWidgets import QSpinBox as _QSB
        self.gpu_layers_spin = _QSB()
        self.gpu_layers_spin.setRange(0, 128)
        self.gpu_layers_spin.setValue(128)
        self.gpu_layers_spin.setSpecialValueText("Auto (all)")
        self.gpu_layers_spin.setToolTip("0 = CPU only, Auto = offload all layers")
        self.gpu_layers_spin.setMinimumHeight(30)
        self.gpu_layers_spin.setFixedWidth(110)
        gpu_layers_row.addWidget(self.gpu_layers_spin)
        gpu_layers_row.addStretch(1)
        layout.addLayout(gpu_layers_row)

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

        params_row = QHBoxLayout()
        self.params_btn = QPushButton("\u2699 Model Params")
        self.params_btn.setObjectName("gpuInstallBtn")
        self.params_btn.setMinimumHeight(34)
        self.params_btn.setEnabled(False)  # enabled once a model loads
        self.params_btn.setToolTip("Per-model sampling + system prompt overrides")
        self.params_btn.clicked.connect(self.params_requested.emit)
        params_row.addWidget(self.params_btn, 1)
        layout.addLayout(params_row)

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

        # Chat search/filter bar
        self.session_search = QWidget()
        search_layout = QHBoxLayout(self.session_search)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(4)
        self.session_search_input = QWidget()
        self.session_search_input.setObjectName("searchInput")
        search_inner = QHBoxLayout(self.session_search_input)
        search_inner.setContentsMargins(6, 2, 6, 2)
        search_inner.setSpacing(4)
        from PySide6.QtWidgets import QLineEdit as _QLE
        self._search_field = _QLE()
        self._search_field.setPlaceholderText("🔍 Search chats...")
        self._search_field.setClearButtonEnabled(True)
        self._search_field.textChanged.connect(self._filter_sessions)
        search_inner.addWidget(self._search_field)
        self.session_search_input.setMinimumHeight(28)
        search_layout.addWidget(self.session_search_input)
        layout.addWidget(self.session_search)

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

    def set_params_enabled(self, enabled: bool) -> None:
        self.params_btn.setEnabled(bool(enabled))

    def set_gpu_layers_max(self, max_layers: int) -> None:
        try:
            self.gpu_layers_spin.setMaximum(max(1, int(max_layers)))
        except Exception:  # noqa: BLE001
            pass

    def get_gpu_layers(self) -> int:
        try:
            v = int(self.gpu_layers_spin.value())
            return -1 if v >= self.gpu_layers_spin.maximum() else v
        except Exception:  # noqa: BLE001
            return -1

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
        self._last_sessions = list(sessions)
        self._last_active_id = active_id
        self.session_list.blockSignals(True)
        self.session_list.clear()
        current_bucket: str | None = None
        for meta in sessions:
            if not meta.get("corrupt"):
                bucket = self._date_bucket(meta.get("updated", ""))
                if bucket != current_bucket:
                    current_bucket = bucket
                    header = QListWidgetItem(f"▸ {bucket}")
                    header.setFlags(Qt.NoItemFlags)
                    header.setForeground(self.palette().color(
                        self.foregroundRole()))
                    self.session_list.addItem(header)
            if meta.get("corrupt"):
                label = f"\u26a0 {meta['id']}"
                item = QListWidgetItem(label)
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                tooltip = f"Corrupt session file: {meta.get('error', '')}"
            else:
                sid = meta["id"]
                is_pending = sid == self._pending_delete_id
                if is_pending:
                    label = f"⚠️ Delete '{meta.get('title') or 'New Chat'}'?\n  ✓ Confirm   ✕ Cancel (3s)"
                    item = QListWidgetItem(label)
                    item.setData(Qt.UserRole, sid)
                    item.setBackground(self.palette().color(self.backgroundRole()).darker(110))
                    tooltip = "Click to confirm delete — auto-cancels after 3 seconds"
                else:
                    title = meta.get("title") or "New Chat"
                    badge = " \U0001F916" if meta.get("mode") == "agent" else ""
                    label = f"{title}{badge}\n{self._relative_time(meta.get('updated', ''))}"
                    item = QListWidgetItem(label)
                    item.setData(Qt.UserRole, sid)
                    if sid == active_id:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                        self.session_list.setCurrentItem(item)
                    tooltip = meta.get("title") or "New Chat"
            item.setToolTip(tooltip)
            self.session_list.addItem(item)
        self.session_list.blockSignals(False)

    def _enter_delete_confirm(self, session_id: str) -> None:
        self._pending_delete_id = session_id
        self._pending_delete_timer.start()
        self.set_sessions(self._last_sessions, self._last_active_id)

    def _confirm_pending_delete(self) -> None:
        if self._pending_delete_id:
            sid = self._pending_delete_id
            self._pending_delete_id = None
            self._pending_delete_timer.stop()
            self.set_sessions(self._last_sessions, self._last_active_id)
            self.session_delete_requested.emit(sid)

    def _cancel_pending_delete(self) -> None:
        if self._pending_delete_id is not None:
            self._pending_delete_id = None
            self._pending_delete_timer.stop()
            self.set_sessions(self._last_sessions, self._last_active_id)

    @staticmethod
    def _date_bucket(iso_stamp: str) -> str:
        """Human grouping for the session list (GPT4All parity, simplified)."""
        try:
            then = datetime.fromisoformat(iso_stamp)
        except (TypeError, ValueError):
            return "Older"
        days = (datetime.now() - then).days
        if days <= 0:
            return "Today"
        if days == 1:
            return "Yesterday"
        if days < 7:
            return "This week"
        if days < 30:
            return "This month"
        if then.year == datetime.now().year:
            return then.strftime("%B")
        return str(then.year)

    def _filter_sessions(self, text: str) -> None:
        """Hide session items that don't match the search text."""
        query = text.strip().lower()
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if not query:
                item.setHidden(False)
                continue
            # Headers always visible when there's a match below them
            item_text = (item.text() or "").lower()
            item.setHidden(query not in item_text and item.data(Qt.UserRole) is not None)
        # Show date headers that have visible items after them
        visible_below = False
        for i in range(self.session_list.count() - 1, -1, -1):
            item = self.session_list.item(i)
            if item.data(Qt.UserRole) is None:
                # Date header - hide if no visible items below
                item.setHidden(not visible_below)
                visible_below = False
            elif not item.isHidden():
                visible_below = True

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.UserRole)
        if not session_id:
            return
        # Two-step delete: clicking the pending item confirms
        if self._pending_delete_id == session_id:
            self._confirm_pending_delete()
            return
        if self._pending_delete_id is not None:
            self._cancel_pending_delete()
        self.session_selected.emit(session_id)

    def _show_session_menu(self, pos) -> None:
        item = self.session_list.itemAt(pos)
        if item is None or not item.data(Qt.UserRole):
            return
        session_id = item.data(Qt.UserRole)
        # If this item is already pending delete, second right-click cancels
        if self._pending_delete_id == session_id:
            self._cancel_pending_delete()
            return
        menu = QMenu(self)
        # Popup windows clear to black on Windows unless themed explicitly.
        from ggufloader.widgets.chat_bubble import _styled_text_menu
        _styled_text_menu(menu, self)
        rename_action = menu.addAction("Rename\u2026")
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(self.session_list.mapToGlobal(pos))
        if chosen is rename_action:
            if self._pending_delete_id is not None:
                self._cancel_pending_delete()
            self.session_rename_requested.emit(session_id)
        elif chosen is delete_action:
            self._enter_delete_confirm(session_id)

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
