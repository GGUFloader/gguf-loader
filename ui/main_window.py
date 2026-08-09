"""
MainWindow - Application composition root.

Owns the three services (model/chat/agent), composes the settings
sidebar and chat panel, provides a menu bar (File/View/Addons/Help),
and exposes the addon-facing API that the old
``AIChat``/``GGUFLoaderApp`` provided:

- ``model``          : callable ModelBackend (or None)
- ``model_loaded``   : Signal(object)
- ``model_unloaded`` : Signal()
- ``generation_finished`` / ``generation_error`` : Signal
- ``chat_generator`` : always None (addons fall back to calling ``model``)
- ``addon_manager``, ``_floating_chat_addon``
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QSplitter, QVBoxLayout, QWidget,
)

from addon_manager import AddonManager
from config import MAX_TOKENS, WINDOW_SIZE, WINDOW_TITLE
from core.llm.model_backend import ModelBackend
from core.llm.prompt_builder import PromptBuilder
from resource_manager import find_icon
from services.agent_service import AgentService
from services.chat_service import ChatService
from services.gpu_install_service import GpuInstallService, is_gpu_support_installed
from services.model_service import ModelService
from ui.chat_panel import ChatPanel
from ui.sidebar_panel import SettingsSidebar
from ui.theme import ThemeMixin

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow, ThemeMixin):
    """Main application window."""

    # Addon-facing signals (kept for backward compatibility)
    model_loaded = Signal(object)
    model_unloaded = Signal()
    generation_finished = Signal()
    generation_error = Signal(str)
    theme_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.is_dark_mode = True  # Dark-first; the toggle in Settings flips it.
        self.chat_generator = None  # Addons check this; None keeps them on the model path.
        self._floating_chat_addon = None

        self._model_service = ModelService(self)
        self._chat_service = ChatService(self)
        self._agent_service = AgentService(self)
        self._gpu_install_service = GpuInstallService(self)
        self._prompt_builder = PromptBuilder()
        self.conversation_history: list[dict] = []

        self._init_window()
        self._build_ui()
        self._wire_services()
        self._load_addons()
        self._populate_addons_menu()
        self._refresh_gpu_support_status()

        logger.info("MainWindow initialized")

    @property
    def model(self) -> Optional[ModelBackend]:
        """Callable model access for the UI and addons (None when unloaded)."""
        return self._model_service.backend

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _init_window(self) -> None:
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(800, 500)
        self.resize(*WINDOW_SIZE)

        icon_path = find_icon("icon.ico")
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))

    def _build_ui(self) -> None:
        self._build_menu_bar()
        self._build_header()

        self.sidebar = SettingsSidebar(self)
        self.sidebar.setObjectName("sidePanel")
        self.chat_panel = ChatPanel(self)

        self.addon_manager = AddonManager()

        splitter = QSplitter()
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.chat_panel)
        splitter.setSizes([300, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self._wire_ui_signals()
        self.apply_styles()
        self.chat_panel.apply_theme(self.is_dark_mode)

    def _build_menu_bar(self) -> None:
        """Top-level menus: File, View (appearance), Addons, Help."""
        bar = self.menuBar()

        # ---- File ----
        file_menu = bar.addMenu("&File")
        action = file_menu.addAction("Load Model\u2026")
        action.triggered.connect(self._choose_and_load_model)
        action = file_menu.addAction("Clear Chat")
        action.triggered.connect(self._clear_chat)
        file_menu.addSeparator()
        action = file_menu.addAction("Exit")
        action.triggered.connect(self.close)

        # ---- View ----
        view_menu = bar.addMenu("&View")
        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        # setChecked before connect: the handler touches self.chat_panel,
        # which does not exist yet while the menu bar is being built.
        self.dark_mode_action.setChecked(self.is_dark_mode)
        self.dark_mode_action.toggled.connect(self._on_dark_mode_toggled)
        view_menu.addAction(self.dark_mode_action)

        text_menu = view_menu.addMenu("Text Size")
        self._text_size_actions: dict[int, QAction] = {}
        for size in (12, 14, 16, 18, 20, 22):
            action = QAction(str(size), self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked, s=size: self._set_text_size(s))
            text_menu.addAction(action)
            self._text_size_actions[size] = action
        self._text_size_actions[14].setChecked(True)

        # ---- Addons (filled after loading) ----
        self.addons_menu = bar.addMenu("&Addons")

        # ---- Help ----
        help_menu = bar.addMenu("&Help")
        action = help_menu.addAction("Send Feedback")
        action.triggered.connect(self._show_feedback_dialog)
        help_menu.addSeparator()
        action = help_menu.addAction("About GGUF Loader")
        action.triggered.connect(self._show_about)

    def _set_text_size(self, size: int) -> None:
        """Apply a text size and keep the View menu checkmarks in sync."""
        for s, action in self._text_size_actions.items():
            action.setChecked(s == size)
        self.chat_panel.apply_font_size(size)
        self.chat_panel.agent_panel.apply_font_size(size)

    def _show_about(self) -> None:
        from __init__ import __version__
        QMessageBox.about(
            self,
            "About GGUF Loader",
            f"<b>GGUF Loader</b> v{__version__}<br>"
            "Local LLM runtime for GGUF models.<br><br>"
            "Built by Hussain Nazary \u00B7 @hussainnazary2",
        )

    def _populate_addons_menu(self) -> None:
        """Rebuild the Addons menu from the loaded addons."""
        self.addons_menu.clear()
        addons = self.addon_manager.get_loaded_addons()
        if not addons:
            action = self.addons_menu.addAction("No addons found")
            action.setEnabled(False)
        else:
            for name in sorted(addons):
                action = self.addons_menu.addAction(name)
                action.triggered.connect(
                    lambda _checked, n=name: self.addon_manager.open_addon_dialog(n, self)
                )
        self.addons_menu.addSeparator()
        action = self.addons_menu.addAction("Refresh Addons")
        action.triggered.connect(self._refresh_addons)

    def _refresh_addons(self) -> None:
        self.addon_manager.load_all_addons()
        self._populate_addons_menu()

    def _build_header(self) -> None:
        """App header: brand on the left, live model status chip on the right."""
        self.header = QFrame()
        self.header.setObjectName("headerBar")
        self.header.setFixedHeight(58)

        layout = QHBoxLayout(self.header)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(12)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        title = QLabel("\U0001F999 GGUF Loader")
        title.setObjectName("brandTitle")
        brand.addWidget(title)
        subtitle = QLabel("Local LLM runtime")
        subtitle.setObjectName("brandSub")
        brand.addWidget(subtitle)
        layout.addLayout(brand)
        layout.addStretch(1)

        self.model_chip = QLabel("\u25CB No model loaded")
        self.model_chip.setObjectName("statusChip")
        layout.addWidget(self.model_chip)

    def _wire_ui_signals(self) -> None:
        s = self.sidebar
        s.load_model_requested.connect(self._choose_and_load_model)
        s.install_gpu_requested.connect(self._install_gpu_support)
        s.gpu_toggled.connect(self._on_gpu_toggled)

        p = self.chat_panel
        p.message_submitted.connect(self._send_message)
        p.agent_mode_toggled.connect(self._on_agent_mode_toggled)
        p.workspace_selected.connect(lambda _path: self._maybe_init_agent())
        p.workspace_browse_btn.clicked.connect(self._browse_workspace)

    def _wire_services(self) -> None:
        m = self._model_service
        m.loading.connect(self.sidebar.set_status)
        m.loaded.connect(self._on_model_loaded)
        m.error.connect(self._on_model_error)
        m.unloaded.connect(self._on_model_unloaded)
        m.unloaded.connect(self.model_unloaded.emit)

        c = self._chat_service
        c.token_received.connect(self.chat_panel.stream_token)
        c.finished.connect(self._on_generation_finished)
        c.error.connect(self._on_generation_error)

        a = self._agent_service
        a.response_generated.connect(self._on_agent_response)
        a.tool_executed.connect(self._on_agent_tool_executed)
        a.token_received.connect(self._on_agent_token)
        a.approval_requested.connect(self._on_agent_approval)
        a.cancelled.connect(self._on_agent_cancelled)
        a.error_occurred.connect(self._on_agent_error)
        a.processing_started.connect(lambda: self.chat_panel.set_agent_status("🟡 Processing..."))
        a.processing_finished.connect(lambda: self.chat_panel.set_agent_status("🟢 Ready"))
        a.status_update.connect(self._on_agent_status)

        g = self._gpu_install_service
        g.output.connect(self.sidebar.append_gpu_output)
        g.finished.connect(self._on_gpu_install_finished)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------
    def _choose_and_load_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select GGUF Model File", "", "GGUF Files (*.gguf);;All Files (*)"
        )
        if not file_path:
            return
        self._load_model(file_path)

    def _load_model(self, path: str) -> None:
        use_gpu = self.sidebar.get_processing_mode() == "GPU Accelerated"
        n_ctx = self.sidebar.get_context_size()

        self.sidebar.set_loading(True)
        self.sidebar.set_model_info("")
        self.sidebar.set_status("Loading model...")
        self._model_service.load(path, use_gpu=use_gpu, n_ctx=n_ctx)

    def _on_model_loaded(self, backend: ModelBackend) -> None:
        self.sidebar.set_loading(False)
        self.sidebar.set_model_info(f"✅ Loaded: {Path(backend.model_path).name}")
        self.sidebar.set_status("Model ready! Start chatting...")
        self.chat_panel.add_system_message("\U0001F916 AI Assistant loaded and ready to help!")
        self._set_model_chip("ok", f"\u25CF {Path(backend.model_path).name}")
        self.model_loaded.emit(backend)

    def _on_model_error(self, message: str) -> None:
        self.sidebar.set_loading(False)
        self.sidebar.set_status(f"❌ Error: {message}")
        self._set_model_chip("err", "\u25CF Load failed")
        QMessageBox.critical(self, "Model Loading Error", message)

    def _on_model_unloaded(self) -> None:
        self._set_model_chip("", "\u25CB No model loaded")

    def _set_model_chip(self, state: str, text: str) -> None:
        """Update the header chip; *state* is '', 'ok' or 'err' (colors via QSS)."""
        self.model_chip.setText(text)
        self.model_chip.setProperty("state", state)
        self.model_chip.style().unpolish(self.model_chip)
        self.model_chip.style().polish(self.model_chip)

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------
    def _send_message(self, text: str) -> None:
        if not self._model_service.is_loaded:
            QMessageBox.warning(self, "No Model", "Please load a model first.")
            return

        if self.chat_panel.is_agent_mode:
            self._send_to_agent(text)
            return

        self.chat_panel.add_user_message(text)
        self.conversation_history.append({"role": "user", "content": text})

        prompt = self._prompt_builder.build(self.conversation_history, text)
        self.chat_panel.begin_streaming()
        self._chat_service.generate(
            self._model_service.backend,
            prompt,
            stop_tokens=self._prompt_builder.stop_tokens(),
            max_tokens=MAX_TOKENS,
            temperature=0.7,
            top_p=0.9,
            repeat_penalty=1.1,
            top_k=40,
        )

    def _on_generation_finished(self) -> None:
        response = self.chat_panel.finish_streaming()
        if response:
            self.conversation_history.append({"role": "assistant", "content": response})
        self.generation_finished.emit()

    def _on_generation_error(self, message: str) -> None:
        self.chat_panel.finish_streaming()
        self.chat_panel.add_system_message(f"❌ Error: {message}")
        self.generation_error.emit(message)

    def _clear_chat(self) -> None:
        self.conversation_history.clear()
        self.chat_panel.clear_chat()
        self.chat_panel.add_system_message("🤖 Chat cleared. Ready for new conversation!")

    # ------------------------------------------------------------------
    # GPU support installer
    # ------------------------------------------------------------------
    def _refresh_gpu_support_status(self) -> None:
        """Sync the sidebar's GPU button with what's actually installed."""
        self.sidebar.set_gpu_installed(is_gpu_support_installed())

    def _on_gpu_toggled(self, enabled: bool) -> None:
        if not enabled:
            return
        if not is_gpu_support_installed():
            QMessageBox.warning(
                self,
                "GPU Support Missing",
                "GPU support is not installed yet.\n\n"
                "Click 'Install GPU Support' in the sidebar and restart the app "
                "to use GPU acceleration.",
            )
            self.sidebar.gpu_button.setChecked(False)
            return
        backend = self._model_service.backend
        if backend is not None:
            reload_now = QMessageBox.question(
                self,
                "GPU Setting Changed",
                "The GPU setting takes effect when the model is reloaded.\n\n"
                "Reload the current model now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reload_now == QMessageBox.Yes:
                self._load_model(backend.model_path)

    def _install_gpu_support(self) -> None:
        if self._gpu_install_service.is_busy:
            return
        if is_gpu_support_installed():
            self.sidebar.set_gpu_installed(True)
            QMessageBox.information(
                self,
                "GPU Support",
                "GPU support is already installed and will be used "
                "when GPU Acceleration is turned on.",
            )
            return
        self.sidebar.set_gpu_install_busy(True)
        self.sidebar.set_status("Installing GPU support…")
        self._gpu_install_service.run_install()

    def _on_gpu_install_finished(self, success: bool, message: str) -> None:
        self.sidebar.set_gpu_install_busy(False)
        if not success:
            self.sidebar.set_status("❌ " + message)
            self.sidebar.gpu_install_status.setText("❌ " + message)
            QMessageBox.critical(self, "GPU Install Failed", message)
            return

        self.sidebar.set_status("✅ GPU support installed — restart to apply")
        self.sidebar.gpu_install_status.setText("✅ " + message)
        self.sidebar.set_gpu_installed(True)
        restart = QMessageBox.question(
            self,
            "GPU Support Installed",
            "GPU support was installed successfully.\n\n"
            "Restart GGUF Loader now to load the GPU build?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if restart == QMessageBox.Yes:
            self._relaunch()

    def _relaunch(self) -> None:
        """Restart the app with the same interpreter, then close this instance."""
        subprocess.Popen([sys.executable, "main.py"], cwd=Path(__file__).resolve().parent.parent)
        self.close()

    # ------------------------------------------------------------------
    # Agent mode
    # ------------------------------------------------------------------
    def _on_agent_mode_toggled(self, enabled: bool) -> None:
        p = self.chat_panel
        p.show_agent_controls(enabled)
        if not enabled:
            p.set_agent_status("⚪ Ready")
            p.set_placeholder("Type your message here...")
            self._agent_service.stop()
            return

        p.set_placeholder("Type your message to the agent...")
        self.chat_panel.set_agent_panel_visible(enabled)
        if not self._model_service.is_loaded:
            p.set_agent_status("❌ No model")
            self.chat_panel.agent_panel.add_status("⚠️ Please load a model first")
            return
        self._init_agent()

    def _maybe_init_agent(self) -> None:
        if self.chat_panel.is_agent_mode and self._model_service.is_loaded:
            self._init_agent()

    def _init_agent(self) -> None:
        p = self.chat_panel
        workspace = p.get_workspace() or "./agent_workspace"
        p.set_workspace(workspace)
        Path(workspace).mkdir(parents=True, exist_ok=True)

        self._agent_service.create_engine(self._model_service.backend, workspace)
        p.set_agent_status("🟢 Ready")
        self.chat_panel.agent_panel.add_status(f"🤖 Agent mode activated\n📁 Workspace: {workspace}")

    def _browse_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Workspace Directory", str(Path.home()), QFileDialog.Option.ShowDirsOnly
        )
        if path:
            self.chat_panel.set_workspace(path)
            self._maybe_init_agent()

    def _send_to_agent(self, text: str) -> None:
        engine = self._agent_service.engine
        if engine is None:
            self.chat_panel.agent_panel.add_status("⚠️ Agent not initialized")
            return
        panel = self.chat_panel.agent_panel
        panel.add_user_message(text)
        # The graph streams the final answer's tokens into a live bubble.
        panel.begin_streaming()
        self._agent_service.process_message(engine, text)

    def _on_agent_status(self, text: str) -> None:
        self.chat_panel.agent_panel.add_status(text)

    def _on_agent_approval(self, payload: dict, waiter) -> None:
        """Show an approval card; Allow/Deny resolves the graph's interrupt."""
        self.chat_panel.agent_panel.add_approval_card(payload, waiter)

    def _on_agent_token(self, token: str) -> None:
        self.chat_panel.agent_panel.stream_token(token)

    def _on_agent_response(self, response: str) -> None:
        streamed = self.chat_panel.agent_panel.finish_streaming()
        if not streamed:
            self.chat_panel.agent_panel.add_ai_message(response)

    def _on_agent_cancelled(self) -> None:
        panel = self.chat_panel.agent_panel
        panel.finish_streaming()
        panel.mark_cancelled()
        panel.add_status("⏹ Agent run cancelled")

    def _on_agent_tool_executed(self, result: dict) -> None:
        self.chat_panel.agent_panel.add_tool_card(result)

    def _on_agent_error(self, message: str) -> None:
        self.chat_panel.agent_panel.finish_streaming()
        self.chat_panel.agent_panel.add_status(f"❌ Error: {message}")
        self.chat_panel.set_agent_status("🟢 Ready")

    # ------------------------------------------------------------------
    # Appearance / feedback
    # ------------------------------------------------------------------
    def _on_dark_mode_toggled(self, enabled: bool) -> None:
        self.is_dark_mode = enabled
        self.apply_styles()
        self.chat_panel.apply_theme(enabled)
        self.chat_panel.agent_panel.apply_theme(enabled)
        self.theme_changed.emit(enabled)

    def _show_feedback_dialog(self) -> None:
        from widgets.feedback_dialog import FeedbackDialog
        dialog = FeedbackDialog(self, self._load_feedback_endpoint())
        dialog.exec()

    def _load_feedback_endpoint(self) -> str:
        config_file = Path("feedback_config.json")
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding="utf-8"))
                return config.get("endpoint_url", "https://formspree.io/f/YOUR_FORM_ID")
            except Exception as e:
                logger.error("Error loading feedback config: %s", e)
        return "https://formspree.io/f/YOUR_FORM_ID"

    # ------------------------------------------------------------------
    # Addons
    # ------------------------------------------------------------------
    def _load_addons(self) -> None:
        self.addon_manager.load_all_addons()
        for addon_name in self.addon_manager.get_loaded_addons():
            try:
                self.addon_manager.get_addon_widget(addon_name, self)
                logger.info("Initialized addon '%s'", addon_name)
            except Exception as e:
                logger.error("Failed to initialize addon '%s': %s", addon_name, e)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        try:
            if self._floating_chat_addon is not None:
                self._floating_chat_addon.stop()
            self._chat_service.stop()
            self._agent_service.stop()
            self._gpu_install_service.stop()
            self._model_service.unload()
        except Exception as e:
            logger.error("Error during shutdown: %s", e)
        event.accept()
