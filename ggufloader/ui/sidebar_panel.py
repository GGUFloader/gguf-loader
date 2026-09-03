"""
SettingsSidebar - Left-hand panel for model configuration.

Kept deliberately focused: model loading, GPU acceleration and context
length. App-level concerns (appearance, clear chat, feedback, addons)
live in the main window's menu bar, and dependency management lives
entirely in the launcher scripts (launch.sh / launch.bat).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMenu, QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget,
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
    rag_scan_requested = Signal()
    rag_toggled = Signal(bool)
    advanced_settings_requested = Signal()
    agent_settings_requested = Signal()

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

        # B4: Memory estimate before load
        self.memory_estimate = QLabel("")
        self.memory_estimate.setObjectName("memoryEstimate")
        self.memory_estimate.setWordWrap(True)
        self.memory_estimate.setVisible(False)
        layout.addWidget(self.memory_estimate)

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
        # Canonical default is 8192 (core/defaults.py) — not the 32768 max.
        self.context_combo.setCurrentText(str(8192))
        self.context_combo.setMinimumHeight(35)
        layout.addWidget(self.context_combo)

        layout.addWidget(self._section_label("Performance"))

        self.n_batch_spin = QSpinBox()
        self.n_batch_spin.setRange(128, 2048)
        self.n_batch_spin.setSingleStep(64)
        self.n_batch_spin.setValue(512)
        layout.addWidget(self._labeled("Batch size (n_batch)", self.n_batch_spin))

        self.n_threads_spin = QSpinBox()
        self.n_threads_spin.setRange(0, 32)
        self.n_threads_spin.setValue(0)
        self.n_threads_spin.setSpecialValueText("auto")
        layout.addWidget(self._labeled("CPU threads (0=auto)", self.n_threads_spin))

        self.n_keep_spin = QSpinBox()
        self.n_keep_spin.setRange(64, 2048)
        self.n_keep_spin.setSingleStep(64)
        self.n_keep_spin.setValue(512)
        layout.addWidget(self._labeled("Keep tokens (n_keep)", self.n_keep_spin))

        self.flash_attn_check = QCheckBox("Flash Attention")
        self.flash_attn_check.setChecked(True)
        layout.addWidget(self.flash_attn_check)

        # Remember the user touched a knob manually (profile defaults below
        # only prefill knobs the user has NOT already changed).
        self._touched = set()
        for w, name in (
            (self.n_batch_spin, "n_batch"), (self.n_threads_spin, "n_threads"),
            (self.n_keep_spin, "n_keep"),
        ):
            w.valueChanged.connect(lambda _v, n=name: self._touched.add(n))
        self.context_combo.currentIndexChanged.connect(
            lambda _i: self._touched.add("ctx"))
        self.flash_attn_check.toggled.connect(
            lambda _v: self._touched.add("flash_attn"))

        # Advanced Settings button
        self.advanced_btn = QPushButton("⚙ Advanced Settings")
        self.advanced_btn.setObjectName("gpuInstallBtn")
        self.advanced_btn.setMinimumHeight(36)
        self.advanced_btn.setToolTip("GPU layers, model params, LocalDocs RAG, and more")
        self.advanced_btn.clicked.connect(self.advanced_settings_requested.emit)
        layout.addWidget(self.advanced_btn)

        # Agent Settings button
        self.agent_settings_btn = QPushButton("🤖 Agent Settings")
        self.agent_settings_btn.setObjectName("gpuInstallBtn")
        self.agent_settings_btn.setMinimumHeight(36)
        self.agent_settings_btn.setToolTip("Configure agent presets, features, and behavior")
        self.agent_settings_btn.clicked.connect(self.agent_settings_requested.emit)
        layout.addWidget(self.agent_settings_btn)

        # Progress + status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to load model")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        layout.addWidget(self.status_label)

        # Cost/token counter (Aider/SWE-agent/DeepSeek pattern)
        self.stats_label = QLabel("")
        self.stats_label.setObjectName("mutedLabel")
        self.stats_label.setWordWrap(True)
        self.stats_label.setVisible(False)
        layout.addWidget(self.stats_label)
        self._total_tokens = 0
        self._total_cost = 0.0
        self._cache_hit_rate = 0.0
        self._last_ttft_ms = None
        # Approximate cost per 1K tokens (varies by model)
        self._cost_per_1k = 0.002  # $2 per 1M tokens (rough estimate)

        # Agent Health widget (compact, collapsible)
        from ggufloader.widgets.agent_health_widget import AgentHealthWidget
        self.agent_health = AgentHealthWidget()
        self.agent_health.setVisible(False)
        layout.addWidget(self.agent_health)

        # ---- Model Info panel ----
        layout.addWidget(self._section_label("Model Info"))
        self.model_info_panel = QLabel("No model loaded")
        self.model_info_panel.setObjectName("mutedLabel")
        self.model_info_panel.setWordWrap(True)
        self.model_info_panel.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.model_info_panel.setMaximumHeight(80)
        layout.addWidget(self.model_info_panel)

        # ---- File Tree ----
        layout.addWidget(self._section_label("Workspace Files"))
        from ggufloader.widgets.file_tree import FileTree
        self.file_tree = FileTree()
        self.file_tree.setMinimumHeight(120)
        self.file_tree.setMaximumHeight(200)
        self.file_tree.setVisible(False)
        layout.addWidget(self.file_tree)

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
        self.session_list.itemDoubleClicked.connect(self._on_session_double_click)
        layout.addWidget(self.session_list, 1)

        layout.addStretch()

    def _section_label(self, text: str) -> QLabel:
        """Tiny uppercase eyebrow label; the accent color comes from QSS."""
        label = QLabel(text.upper())
        label.setObjectName("sectionEyebrow")
        label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        return label

    def _labeled(self, text: str, widget: QWidget) -> QWidget:
        """Wrap *widget* with a small caption label above it."""
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        cap = QLabel(text)
        cap.setObjectName("mutedLabel")
        v.addWidget(cap)
        v.addWidget(widget)
        return container

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

    def update_model_info_panel(self, info: dict) -> None:
        """Update the detailed model info panel."""
        parts = []
        if info.get("name"):
            parts.append(f"Name: {info['name']}")
        if info.get("arch"):
            parts.append(f"Arch: {info['arch']}")
        if info.get("quant"):
            parts.append(f"Quant: {info['quant']}")
        if info.get("layers"):
            parts.append(f"Layers: {info['layers']}")
        if info.get("ctx"):
            parts.append(f"Context: {info['ctx']:,}")
        if info.get("gpu"):
            parts.append(f"GPU: {info['gpu']}")
        if info.get("vram"):
            parts.append(f"VRAM: {info['vram']}")
        self.model_info_panel.setText("\n".join(parts) if parts else "No model loaded")

    def set_workspace(self, path: str) -> None:
        """Set the workspace for the file tree."""
        self.file_tree.setVisible(bool(path))
        if path:
            self.file_tree.set_workspace(Path(path))

    def set_memory_estimate(self, estimate: dict) -> None:
        """Show memory estimate for a model file before loading."""
        if not estimate:
            self.memory_estimate.setVisible(False)
            return
        model_gb = estimate.get("model_gb", 0)
        kv_gb = estimate.get("kv_gb", 0)
        total_gb = estimate.get("total_gb", 0)
        layers = estimate.get("layers")
        quant = estimate.get("quant", "")
        ram_gb = estimate.get("ram_gb", 0)
        vram_gb = estimate.get("vram_gb", 0)
        fits_ram = estimate.get("fits_ram", True)
        fits_vram = estimate.get("fits_vram", False)

        # Build the estimate text
        parts = [f"📦 Model: {model_gb:.1f} GB"]
        if kv_gb > 0.01:
            parts.append(f"💾 KV cache: {kv_gb:.1f} GB")
        parts.append(f"⚡ Total: {total_gb:.1f} GB")
        if layers:
            parts.append(f"🧱 Layers: {layers}")
        if quant:
            parts.append(f"🔧 Quant: {quant}")

        # Memory warnings
        if not fits_ram and ram_gb > 0:
            parts.append(f"\n⚠️ Requires {total_gb:.1f} GB but only {ram_gb:.0f} GB RAM available")
        elif fits_vram and vram_gb > 0:
            parts.append(f"\n✅ Fits in GPU VRAM ({vram_gb:.0f} GB)")
        elif ram_gb > 0:
            parts.append(f"\n✅ Fits in system RAM ({ram_gb:.0f} GB)")

        self.memory_estimate.setText("\n".join(parts))
        self.memory_estimate.setVisible(True)

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

    def update_token_stats(self, tokens: int) -> None:
        """Update the token/cost counter (Aider/SWE-agent/DeepSeek pattern)."""
        self._total_tokens += tokens
        self._total_cost = self._total_tokens / 1000.0 * self._cost_per_1k
        if self._total_tokens > 0:
            stats_text = f"📊 Tokens: {self._total_tokens:,}  ~${self._total_cost:.4f}"
            # Add TTFT if available
            ttft = getattr(self, '_last_ttft_ms', None)
            if ttft is not None:
                stats_text += f"  ⚡ {ttft}ms TTFT"
            self.stats_label.setText(stats_text)
            self.stats_label.setVisible(True)

    def update_ttft(self, ttft_ms: int) -> None:
        """Update time-to-first-token display (DeepSeek StatsLine pattern)."""
        self._last_ttft_ms = ttft_ms
        # Refresh the stats display
        if self._total_tokens > 0:
            stats_text = f"📊 Tokens: {self._total_tokens:,}  ~${self._total_cost:.4f}  ⚡ {ttft_ms}ms TTFT"
            self.stats_label.setText(stats_text)

    def update_cache_hit(self, hit_rate: float) -> None:
        """Update cache hit rate display (DeepSeek StatsLine pattern)."""
        self._cache_hit_rate = hit_rate
        if self._total_tokens > 0:
            stats_text = f"📊 Tokens: {self._total_tokens:,}  ~${self._total_cost:.4f}"
            if self._cache_hit_rate > 0:
                stats_text += f"  💾 {self._cache_hit_rate:.0%} cache"
            self.stats_label.setText(stats_text)

    def reset_token_stats(self) -> None:
        """Reset token counters for a new session."""
        self._total_tokens = 0
        self._total_cost = 0.0
        self.stats_label.setVisible(False)

    def set_params_enabled(self, enabled: bool) -> None:
        """Enable/disable the per-model params button (now a no-op, kept for compat)."""
        pass  # params button moved to AdvancedSettingsDialog

    def get_gpu_layers(self) -> int:
        """Get GPU layers chosen in the Advanced Settings dialog (-1 = auto)."""
        return getattr(self, "_gpu_layers", -1)

    def set_gpu_layers(self, n_gpu_layers: int) -> None:
        """Store the Advanced dialog's GPU-layer choice for the next load."""
        self._gpu_layers = int(n_gpu_layers)

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

    def update_agent_health(self, health: dict) -> None:
        """Update the agent health widget."""
        self.agent_health.setVisible(True)
        self.agent_health.update_health(health)

    def get_context_size(self) -> int:
        try:
            return int(self.context_combo.currentText())
        except ValueError:
            return 8192  # canonical default (core/defaults.DEFAULT_CTX)

    def get_performance_params(self) -> dict:
        """Return n_batch / n_threads / n_keep / flash_attn from the sidebar."""
        return {
            "n_batch": self.n_batch_spin.value(),
            "n_threads": self.n_threads_spin.value() or None,
            "n_keep": self.n_keep_spin.value(),
            "flash_attn": self.flash_attn_check.isChecked(),
        }

    def apply_profile_defaults(self, profile) -> None:
        """Prefill performance knobs from a ModelProfile (only if user hasn't touched them)."""
        touched = getattr(self, "_touched", set())
        if "n_batch" not in touched:
            self.n_batch_spin.setValue(getattr(profile, "n_batch", 512))
        if "n_keep" not in touched:
            self.n_keep_spin.setValue(getattr(profile, "n_keep", 512))
        if "flash_attn" not in touched:
            self.flash_attn_check.setChecked(getattr(profile, "flash_attn", True))

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

    def _on_session_double_click(self, item: QListWidgetItem) -> None:
        """Double-click a session to rename it."""
        session_id = item.data(Qt.UserRole)
        if not session_id:
            return
        self.session_rename_requested.emit(session_id)

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
