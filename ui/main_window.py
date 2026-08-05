"""
MainWindow - Application composition root.

Owns the three services (model/chat/agent), composes the settings
sidebar, chat panel and addon sidebar, and exposes the addon-facing API
that the old ``AIChat``/``GGUFLoaderApp`` provided:

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
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog, QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget,
)

from addon_manager import AddonManager, AddonSidebarFrame
from config import MAX_TOKENS, WINDOW_SIZE, WINDOW_TITLE
from core.llm.model_backend import ModelBackend
from core.llm.prompt_builder import PromptBuilder
from resource_manager import find_icon
from services.agent_service import AgentService
from services.chat_service import ChatService
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

    def __init__(self) -> None:
        super().__init__()
        self.is_dark_mode = False
        self.chat_generator = None  # Addons check this; None keeps them on the model path.
        self._floating_chat_addon = None

        self._model_service = ModelService(self)
        self._chat_service = ChatService(self)
        self._agent_service = AgentService(self)
        self._prompt_builder = PromptBuilder()
        self.conversation_history: list[dict] = []

        self._init_window()
        self._build_ui()
        self._wire_services()
        self._load_addons()

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
        self.sidebar = SettingsSidebar(self)
        self.chat_panel = ChatPanel(self)

        self.addon_manager = AddonManager()
        addon_sidebar = AddonSidebarFrame(self.addon_manager, self)

        splitter = QSplitter()
        splitter.addWidget(addon_sidebar)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.chat_panel)
        splitter.setSizes([200, 280, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)
        self.setCentralWidget(splitter)

        self._wire_ui_signals()
        self.apply_styles()

    def _wire_ui_signals(self) -> None:
        s = self.sidebar
        s.load_model_requested.connect(self._choose_and_load_model)
        s.dark_mode_toggled.connect(self._on_dark_mode_toggled)
        s.text_size_changed.connect(self.chat_panel.apply_font_size)
        s.clear_chat_requested.connect(self._clear_chat)
        s.feedback_requested.connect(self._show_feedback_dialog)

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
        m.unloaded.connect(self.model_unloaded.emit)

        c = self._chat_service
        c.token_received.connect(self.chat_panel.stream_token)
        c.finished.connect(self._on_generation_finished)
        c.error.connect(self._on_generation_error)

        a = self._agent_service
        a.response_generated.connect(self._on_agent_response)
        a.tool_executed.connect(self._on_agent_tool_executed)
        a.error_occurred.connect(self._on_agent_error)
        a.processing_started.connect(lambda: self.chat_panel.set_agent_status("🟡 Processing..."))
        a.processing_finished.connect(lambda: self.chat_panel.set_agent_status("🟢 Ready"))
        a.status_update.connect(self.chat_panel.add_system_message)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------
    def _choose_and_load_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select GGUF Model File", "", "GGUF Files (*.gguf);;All Files (*)"
        )
        if not file_path:
            return

        use_gpu = self.sidebar.get_processing_mode() == "GPU Accelerated"
        n_ctx = self.sidebar.get_context_size()

        self.sidebar.set_loading(True)
        self.sidebar.set_model_info("")
        self.sidebar.set_status("Loading model...")
        self._model_service.load(file_path, use_gpu=use_gpu, n_ctx=n_ctx)

    def _on_model_loaded(self, backend: ModelBackend) -> None:
        self.sidebar.set_loading(False)
        self.sidebar.set_model_info(f"✅ Loaded: {Path(backend.model_path).name}")
        self.sidebar.set_status("Model ready! Start chatting...")
        self.chat_panel.add_system_message("🤖 AI Assistant loaded and ready to help!")
        self.model_loaded.emit(backend)

    def _on_model_error(self, message: str) -> None:
        self.sidebar.set_loading(False)
        self.sidebar.set_status(f"❌ Error: {message}")
        QMessageBox.critical(self, "Model Loading Error", message)

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
        if not self._model_service.is_loaded:
            p.set_agent_status("❌ No model")
            p.add_system_message("⚠️ Please load a model first")
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
        p.add_system_message(f"🤖 Agent mode activated\n📁 Workspace: {workspace}")

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
            self.chat_panel.add_system_message("⚠️ Agent not initialized")
            return
        self.chat_panel.add_user_message(text)
        self._agent_service.process_message(engine, text)

    def _on_agent_response(self, response: str) -> None:
        self.chat_panel.add_ai_message(response)

    def _on_agent_tool_executed(self, result: dict) -> None:
        tool = result.get("tool_name", "unknown")
        if result.get("status") == "success":
            if tool == "write_file":
                self.chat_panel.add_system_message(
                    f"✅ Wrote {result.get('bytes_written', 0)} bytes to {result.get('path', 'file')}")
            elif tool == "edit_file":
                self.chat_panel.add_system_message(
                    f"✅ {result.get('operation', 'edit')}: {result.get('changes_made', 0)} change(s)")
            elif tool == "read_file":
                self.chat_panel.add_system_message(f"✅ Read {result.get('lines', 0)} lines")
            elif tool == "list_directory":
                self.chat_panel.add_system_message(
                    f"✅ Listed directory ({len(result.get('result', []))} items)")
            elif tool == "search_files":
                self.chat_panel.add_system_message(
                    f"✅ Search completed ({result.get('total_matches', 0)} matches)")
            else:
                self.chat_panel.add_system_message(f"✅ {tool} completed")
        else:
            self.chat_panel.add_system_message(f"❌ {tool} failed: {result.get('error', 'Unknown error')}")

    def _on_agent_error(self, message: str) -> None:
        self.chat_panel.add_system_message(f"❌ Error: {message}")
        self.chat_panel.set_agent_status("🟢 Ready")

    # ------------------------------------------------------------------
    # Appearance / feedback
    # ------------------------------------------------------------------
    def _on_dark_mode_toggled(self, enabled: bool) -> None:
        self.is_dark_mode = enabled
        self.apply_styles()
        self.chat_panel.apply_theme(enabled)

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
        results = self.addon_manager.load_all_addons()
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
            self._model_service.unload()
        except Exception as e:
            logger.error("Error during shutdown: %s", e)
        event.accept()
