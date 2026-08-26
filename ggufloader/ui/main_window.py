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
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, Signal, QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QMainWindow, QMenu, QMessageBox, QSplitter, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from ggufloader.addon_manager import AddonManager
from ggufloader.config import (
    CHAT_MAX_TOKENS, MIN_WINDOW_SIZE, WINDOW_SIZE, WINDOW_TITLE, get_paths,
)
from ggufloader.core.llm.model_backend import ModelBackend
from ggufloader.core.llm.model_params import load_model_params
from ggufloader.core.llm.model_profiles import read_model_limits, resolve_chat_config
from ggufloader.core.llm.prompt_builder import PromptBuilder
from ggufloader.core.sessions import SessionStore
from ggufloader.resource_manager import find_icon
from ggufloader.services.agent_service import AgentService
from ggufloader.services.chat_service import ChatService
from ggufloader.services.gpu_install_service import GpuInstallService, is_gpu_support_installed
from ggufloader.services.model_service import ModelService
from ggufloader.ui.chat_panel import ChatPanel
from ggufloader.ui.sidebar_panel import SettingsSidebar
from ggufloader.ui.theme import ThemeMixin

logger = logging.getLogger(__name__)

# Verbatim from GPT4All's ModelInfo defaults (modellist.h:276) - proven to
# produce tight names across small models.
CHAT_NAME_PROMPT = (
    "Describe the above conversation. Your entire response must be "
    "three words or less."
)


class _TitleBridge(QObject):
    """Queued-connection bridge for title generation on a worker thread."""

    title_ready = Signal(str, str)  # session_id, title

    def emit_title(self, session_id: str, title: str) -> None:
        self.title_ready.emit(session_id, title)


class _FollowupBridge(QObject):
    questions_ready = Signal(list)

    def emit_questions(self, questions: list) -> None:
        self.questions_ready.emit(questions)


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
        self.is_dark_mode = False  # Light-first; the Dark Mode toggle in View flips it.
        self.chat_generator = None  # Addons check this; None keeps them on the model path.
        self._floating_chat_addon = None

        self._model_service = ModelService(self)
        self._chat_service = ChatService(self)
        self._agent_service = AgentService(self)
        self._gpu_install_service = GpuInstallService(self)
        self._prompt_builder = PromptBuilder()
        self.conversation_history: list[dict] = []
        self._store = SessionStore(get_paths()["chats"])
        self._session: Optional[dict] = None
        self._current_session_id: Optional[str] = None
        # Auto-configured per loaded model (see _apply_model_profile).
        self._chat_model_params: dict = {}
        self._chat_system_prompt: Optional[str] = None
        self._naming_busy = False
        self._followups_busy = False
        self._title_bridge = _TitleBridge()
        self._title_bridge.title_ready.connect(self._on_title_ready)
        self._followup_bridge = _FollowupBridge()

        self._init_window()
        self._build_ui()
        self._wire_services()
        self._load_addons()
        self._populate_addons_menu()
        self._refresh_gpu_support_status()
        self._restore_last_session()

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
        self.setMinimumSize(*MIN_WINDOW_SIZE)
        self._settings = QSettings("GGUFLoader", "App")
        geo = self._settings.value("window_geometry")
        restored = False
        if isinstance(geo, (bytes, bytearray, str)) and geo:
            try:
                if self.restoreGeometry(
                    bytes.fromhex(geo) if isinstance(geo, str) else bytes(geo)
                ):
                    restored = True
            except Exception:  # noqa: BLE001 - corrupt geometry is ignorable
                restored = False
        if not restored:
            self.resize(*WINDOW_SIZE)

        icon_path = find_icon("icon.ico")
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))
        self._tray_icon = self._build_tray(icon_path)

    def _build_tray(self, icon_path: str):
        """System tray with Show/Quit; minimize-to-tray toggle in View menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray = QSystemTrayIcon(QIcon(icon_path) if Path(icon_path).exists() else QIcon(), self)
        menu = QMenu()
        show_action = menu.addAction("Show GGUF Loader")
        quit_action = menu.addAction("Quit")
        show_action.triggered.connect(self._show_from_tray)
        quit_action.triggered.connect(self.close)
        tray.setContextMenu(menu)
        tray.setToolTip(WINDOW_TITLE)
        tray.activated.connect(lambda reason:
                               self._show_from_tray() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        tray.show()
        return tray

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        # Persist window geometry for the next launch.
        self._settings.setValue("window_geometry",
                                bytes(self.saveGeometry().toBase64()).hex())
        if self._minimize_to_tray_action.isChecked() and \
                getattr(self, "_tray_icon", None) is not None:
            event.ignore()
            self.hide()
            return
        super().closeEvent(event)

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
        action = file_menu.addAction("Copy Conversation")
        action.triggered.connect(self._copy_conversation)
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

        self._minimize_to_tray_action = QAction("Minimize to tray", self)
        self._minimize_to_tray_action.setCheckable(True)
        self._minimize_to_tray_action.setChecked(
            self._settings.value("minimize_to_tray", "false") in (True, "true", "1")
        )
        self._minimize_to_tray_action.toggled.connect(
            lambda v: self._settings.setValue("minimize_to_tray", bool(v)))
        view_menu.addAction(self._minimize_to_tray_action)

        text_menu = view_menu.addMenu("Text Size")
        self._text_size_actions: dict[int, QAction] = {}
        for size in (12, 14, 16, 18, 20, 22):
            action = QAction(str(size), self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked, s=size: self._set_text_size(s))
            text_menu.addAction(action)
            self._text_size_actions[size] = action
        self._text_size_actions[14].setChecked(True)

        # ---- Tools ----
        tools_menu = bar.addMenu("&Tools")
        action = tools_menu.addAction("Find Paragraph\u2026")
        action.triggered.connect(self._show_find_dialog)

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

    def _show_find_dialog(self) -> None:
        """Open the Find Paragraph dialog (searches a document with the model)."""
        from ggufloader.ui.find_dialog import FindParagraphDialog
        default_folder = self.chat_panel.get_workspace()
        dlg = FindParagraphDialog(self._model_service, self, default_folder=default_folder)
        dlg.exec()

    def _show_about(self) -> None:
        from ggufloader import __version__
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
        p.stop_requested.connect(self._stop_generation)
        p.regenerate_requested.connect(self._regenerate_last)
        p.edit_last_requested.connect(self._edit_last_prompt)
        p.feedback_requested.connect(self._on_feedback)
        s.context_combo.currentIndexChanged.connect(self._on_context_changed)
        s.params_requested.connect(self._open_model_params)

        self.sidebar.new_chat_requested.connect(self._on_new_chat)
        self.sidebar.session_selected.connect(self._on_session_selected)
        self.sidebar.session_rename_requested.connect(self._on_session_rename)
        self.sidebar.session_delete_requested.connect(self._on_session_delete)
        self._followup_bridge.questions_ready.connect(
            self.chat_panel.show_followups)

    def _wire_services(self) -> None:
        m = self._model_service
        m.loading.connect(self.sidebar.set_status)
        m.loaded.connect(self._on_model_loaded)
        m.error.connect(self._on_model_error)
        m.unloaded.connect(self._on_model_unloaded)
        m.unloaded.connect(self.model_unloaded.emit)

        c = self._chat_service
        c.started.connect(lambda: self.chat_panel.set_generating(True))
        c.finished.connect(lambda: self.chat_panel.set_generating(False))
        c.error.connect(lambda _m: self.chat_panel.set_generating(False))
        c.token_received.connect(self.chat_panel.stream_token)
        c.finished.connect(self._on_generation_finished)
        c.error.connect(self._on_generation_error)

        a = self._agent_service
        a.processing_started.connect(lambda: self.chat_panel.set_generating(True))
        a.processing_finished.connect(lambda: self.chat_panel.set_generating(False))

        self.model_loaded.connect(lambda _backend: self._maybe_init_agent())

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

    def _on_context_changed(self, _index: int) -> None:
        """Context changes only take effect when the model is reloaded."""
        if self._model_service.is_loaded:
            self.sidebar.set_status(
                "ℹ️ Reload the model (Load GGUF Model) to apply the new context size."
            )

    def _apply_model_profile(self, backend: ModelBackend) -> str:
        """Detect the model family and auto-configure chat for it.

        Returns a human-readable detection line for the sidebar.
        """
        try:
            config = resolve_chat_config(backend.model_path)
        except Exception as e:  # noqa: BLE001 - never block chat on routing
            logger.warning("Model-profile detection failed: %s", e)
            config = {"label": "Generic instruct", "detected_via": "fallback",
                      "params": {}, "system_prompt": None}
        self._chat_model_params = dict(config.get("params") or {})
        self._chat_model_params.setdefault("max_tokens", CHAT_MAX_TOKENS)
        self._chat_system_prompt = config.get("system_prompt")

        # ---- M3: embedding models are not chat models ----
        extra = ""
        if config.get("is_embedding_model"):
            extra += ("\nℹ️ This looks like an *embedding* model — it cannot "
                      "converse. Load a chat/instruct GGUF instead.")
        # O5: warn when file size may exceed available memory
        try:
            from ggufloader.utils import get_system_ram_bytes
            ram = get_system_ram_bytes()
            fsize = Path(backend.model_path).stat().st_size if Path(backend.model_path).exists() else 0
            if ram and fsize and fsize > ram * 0.55:
                gb = fsize / (1024 ** 3)
                ram_gb = ram / (1024 ** 3)
                extra += (f"\n⚠️ Model size {gb:.1f} GB is large for {ram_gb:.0f} GB RAM — "
                          "expect slow loading or swapping. Try a smaller quant.")
        except Exception:  # noqa: BLE001
            pass

        # ---- GPU honesty (B1) + GGUF limits (B3) ----
        gpu = backend.gpu_status
        if gpu["state"] == "gpu":
            gpu_line = "\n🎮 GPU offload: on (all layers)"
        elif gpu["state"] == "cpu_fallback":
            gpu_line = f"\n⚠️ Running on CPU — {gpu['reason']}. " \
                       "Install the GPU build for full speed."
        else:
            gpu_line = "\n⚙ Running on CPU (GPU Acceleration off)"
        limits = read_model_limits(backend.model_path)
        max_ctx = limits.get("max_context")
        limit_line = ""
        trained = backend.n_ctx_train or max_ctx
        if trained and self.sidebar.get_context_size() > trained:
            limit_line = (
                f"\n⚠️ Context {self.sidebar.get_context_size()} exceeds what this "
                f"model was trained for ({trained} tokens) — expect degraded output. "
                "Pick a smaller context or a longer-context model."
            )
        return (
            f"\n🧭 Auto-config: {config.get('label')} "
            f"({config.get('detected_via')}) · "
            f"temp {self._chat_model_params.get('temperature')}"
            f"{gpu_line}{limit_line}{extra}"
        )

    def _on_model_loaded(self, backend: ModelBackend) -> None:
        self.sidebar.set_loading(False)
        info = f"✅ Loaded: {Path(backend.model_path).name}"
        info += self._apply_model_profile(backend)
        self.sidebar.set_model_info(info)
        self.sidebar.set_params_enabled(True)
        self.sidebar.set_status("Model ready! Start chatting...")

    def _open_model_params(self) -> None:
        """C1-lite dialog: per-model sampling + system prompt overrides."""
        backend = self._model_service.backend
        if not self._model_service.is_loaded or backend is None:
            QMessageBox.information(self, "No Model", "Load a model first.")
            return
        from ggufloader.ui.model_params_dialog import ModelParamsDialog
        dlg = ModelParamsDialog(
            self, backend.model_path,
            current_params=self._chat_model_params,
            current_system_prompt=self._chat_system_prompt,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        # Re-resolve: file override now reflects the dialog's save/reset.
        self._apply_model_profile(backend)
        sp = dlg.system_prompt_override()
        if sp:
            self._chat_system_prompt = sp
        self._on_model_loaded(backend)
        self.chat_panel.add_system_message("\U0001F916 AI Assistant loaded and ready to help!")
        self._set_model_chip("ok", f"\u25CF {Path(backend.model_path).name}")
        self.model_loaded.emit(backend)

    def _on_model_error(self, message: str) -> None:
        self.sidebar.set_loading(False)
        self.sidebar.set_status(f"❌ Error: {message}")
        self._set_model_chip("err", "\u25CF Load failed")
        QMessageBox.critical(self, "Model Loading Error", message)

    def _on_model_unloaded(self) -> None:
        self.sidebar.set_params_enabled(False)
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

        self._ensure_current_session("chat")
        self._store.append_message(self._session, "user", text)
        self._save_session_quiet()
        self._refresh_session_list()

        self.chat_panel.add_user_message(text)
        self.conversation_history.append({"role": "user", "content": text})
        self._generate_reply(text)

    def _generate_reply(self, user_text: str) -> None:
        """Stream an assistant reply for an already-recorded user turn."""
        # Automatic model routing: detect family from GGUF metadata /
        # filename, apply its recommended sampling + system prompt, then
        # let the user's model_params.json override anything.
        messages = self._prompt_builder.build_messages(
            self.conversation_history[:-1], user_text,
            system_prompt=self._chat_system_prompt,
        )
        params = {
            "max_tokens": CHAT_MAX_TOKENS,
            **self._chat_model_params,
        }
        messages, trimmed, too_long = self._fit_messages_to_context(messages, params)
        if too_long:
            self.chat_panel.add_system_message(
                "⚠️ This message is too long for the current context window. "
                "Shorten it or raise the context size in the sidebar."
            )
            return
        if trimmed:
            self.chat_panel.add_system_message(
                "ℹ️ Older messages were trimmed to fit the context window."
            )
        self.chat_panel.begin_streaming()
        self._chat_service.generate(self._model_service.backend, messages=messages, **params)

    def _stop_generation(self) -> None:
        """Stop button: cancel whatever stream is active."""
        self._chat_service.stop()
        self._agent_service.stop()
        self.chat_panel.set_generating(False)
        self.chat_panel.agent_panel.finish_streaming()

    def _on_feedback(self, status: str, message_text: str) -> None:
        """K5: persist 👍/👎 (with optional better-response) on the session."""
        if self._session is None:
            self.chat_panel.add_system_message(
                "ℹ️ Feedback needs a saved session — send a message first.")
            return
        note = None
        if status == "down":
            note, _ = QInputDialog.getMultiLineText(
                self, "Bad response",
                "Optionally write a better response:", "")
        if self._store.set_last_assistant_feedback(
                self._session, message_text, status, note):
            self._save_session_quiet()
            emoji = "👍" if status == "up" else "👎"
            self.chat_panel.add_system_message(f"{emoji} Feedback saved.")
        else:
            self.chat_panel.add_system_message("⚠️ Could not match that reply in this session.")

    def _pop_last_exchange_records(self) -> Optional[str]:
        """Drop the newest user+assistant pair from history and session."""
        hist = self.conversation_history
        if len(hist) < 2 or hist[-1].get("role") != "assistant" \
                or hist[-2].get("role") != "user":
            return None
        assistant_msg = hist.pop()
        user_msg = hist.pop()
        if self._session is not None:
            msgs = self._session.get("messages") or []
            if msgs and msgs[-1].get("role") == "assistant":
                msgs.pop()
            if msgs and msgs[-1].get("role") == "user":
                msgs.pop()
            self._save_session_quiet()
        return user_msg.get("content", "")

    def _regenerate_last(self) -> None:
        """Re-run the newest exchange (GPT4All 'Redo' parity)."""
        if getattr(self.chat_panel, "_generating", False):
            return
        if not self._model_service.is_loaded:
            return
        user_text = self._pop_last_exchange_records()
        if user_text is None:
            self.chat_panel.add_system_message("ℹ️ Nothing to regenerate yet.")
            return
        self.chat_panel.pop_last_exchange()
        self._refresh_session_list()
        self.conversation_history.append({"role": "user", "content": user_text})
        if self._session is not None:
            self._store.append_message(self._session, "user", user_text)
            self._save_session_quiet()
        self._generate_reply(user_text)

    def _edit_last_prompt(self, text: str) -> None:
        """Pop the newest exchange back into the composer for editing."""
        if getattr(self.chat_panel, "_generating", False):
            return
        hist = self.conversation_history
        is_last = (len(hist) >= 2 and hist[-1].get("role") == "assistant"
                   and hist[-2].get("role") == "user"
                   and hist[-2].get("content") == text)
        if not is_last:
            self.chat_panel.add_system_message(
                "ℹ️ Only the most recent message can be edited."
            )
            return
        popped = self._pop_last_exchange_records()
        self.chat_panel.pop_last_exchange()
        self._refresh_session_list()
        self.chat_panel.refill_input(popped if popped is not None else text)

    def _fit_messages_to_context(
        self, messages: list[dict], params: dict
    ) -> tuple[list[dict], bool, bool]:
        """Trim oldest turns so prompt fits n_ctx minus the reply budget.

        Returns ``(messages, trimmed, too_long)``. ``too_long`` means even
        the newest exchange cannot fit - the caller refuses to send.
        """
        backend = self._model_service.backend
        n_ctx = (backend.n_ctx if backend is not None else None) or 32768
        budget = max(256, n_ctx - int(params.get("max_tokens", 2048)) - 64)
        if backend is None:
            return messages, False, False

        def total(msgs: list[dict]) -> int:
            return sum(backend.count_tokens(m.get("content", "")) for m in msgs) \
                + len(msgs) * 4  # per-message template overhead

        if total(messages) <= budget:
            return messages, False, False

        system = messages[:1]
        rest = messages[1:]
        # Newest message alone must fit; otherwise refuse.
        if total([system[0], rest[-1]]) > budget:
            return messages, False, True
        while len(rest) > 1 and total(system + rest) > budget:
            rest.pop(0)
        return system + rest, True, False

    def _on_generation_finished(self) -> None:
        response = self.chat_panel.finish_streaming()
        if response:
            self.conversation_history.append({"role": "assistant", "content": response})
            if self._session is not None:
                self._store.append_message(self._session, "assistant", response)
                # D1: persist thinking duration when the model reasoned.
                ms = getattr(self.chat_panel, "last_thinking_ms", None)
                if ms is not None:
                    msgs = self._session.get("messages") or []
                    if msgs and msgs[-1].get("role") == "assistant":
                        msgs[-1]["thinking_ms"] = int(ms)
                self._save_session_quiet()
                self._refresh_session_list()
                self._maybe_generate_title(response)
                if not self.chat_panel.is_agent_mode:
                    self._maybe_generate_followups(response)
        elif getattr(self.chat_panel, "stopped_in_reasoning", False):
            self.chat_panel.add_system_message(
                "⚠️ The model hit the token limit while still reasoning and never "
                "reached an answer. Try a shorter question or raise the token budget."
            )
        self.generation_finished.emit()

    def _maybe_generate_title(self, assistant_reply: str) -> None:
        """Async LLM title for unnamed sessions (GPT4All D2 parity)."""
        if self._naming_busy or self._session is None or self._session.get("title"):
            return
        session_id = self._session["id"]
        user_q = next((m.get("content", "") for m in
                       reversed(self.conversation_history)
                       if m.get("role") == "user"), "")[:500]
        reply = (assistant_reply or "")[:800]
        if not user_q.strip():
            return
        self._naming_busy = True

        def work() -> None:
            try:
                backend = self._model_service.backend
                out = backend.chat(
                    [{"role": "user", "content":
                        CHAT_NAME_PROMPT + f"\n\nUser: {user_q}\n\nAssistant: {reply}"}],
                    max_tokens=24,
                    temperature=0.2, top_k=80, top_p=0.9,
                )
                words = " ".join(out.split()).strip().strip('"').strip(".")
                title = " ".join(words.split()[:3]) if words else ""
                if title and not getattr(self, "_naming_cancelled", False):
                    self._title_bridge.emit_title(session_id, title)
            except Exception as e:  # noqa: BLE001 - naming must never break chat
                logger.debug("Title generation failed: %s", e)
            finally:
                self._naming_busy = False

        threading.Thread(target=work, daemon=True).start()

    def _on_title_ready(self, session_id: str, title: str) -> None:
        """Apply a generated title unless the session vanished/renamed."""
        session = self._store.load(session_id)
        if session is None or session.get("title"):
            return  # renamed manually or deleted meanwhile
        self._store.rename(session_id, title)
        if self._current_session_id == session_id and self._session is not None \
                and not self._session.get("title"):
            self._session["title"] = title
        self._refresh_session_list()

    def _maybe_generate_followups(self, assistant_reply: str) -> None:
        """Async suggested-follow-up chips (GPT4All D3 parity)."""
        from ggufloader.core.llm.followups import FOLLOWUP_PROMPT, extract_questions
        if self._followups_busy or not assistant_reply.strip():
            return
        last_user = next((m.get("content", "") for m in
                          reversed(self.conversation_history)
                          if m.get("role") == "user"), "")[:500]
        if not last_user:
            return
        self._followups_busy = True

        def work() -> None:
            try:
                backend = self._model_service.backend
                out = backend.chat(
                    [{"role": "user", "content":
                        FOLLOWUP_PROMPT + f"\n\nUser: {last_user}\n\nAssistant: {assistant_reply[:600]}"}],
                    max_tokens=140,
                    temperature=0.3, top_k=80, top_p=0.9,
                )
                qs = extract_questions(out)
                if qs:
                    self._followup_bridge.emit_questions(qs)
            except Exception as e:  # noqa: BLE001
                logger.debug("Followup generation failed: %s", e)
            finally:
                self._followups_busy = False

        threading.Thread(target=work, daemon=True).start()

    def _on_generation_error(self, message: str) -> None:
        self.chat_panel.finish_streaming()
        self.chat_panel.add_system_message(f"❌ Error: {message}")
        self.generation_error.emit(message)

    def _copy_conversation(self) -> None:
        """Whole transcript to the clipboard (GPT4All parity)."""
        text = self.chat_panel.copy_conversation()
        if text:
            QApplication.clipboard().setText(text)
            self.chat_panel.add_system_message("📋 Conversation copied to clipboard.")

    def _clear_chat(self) -> None:
        self.conversation_history.clear()
        if self._session is not None:
            self._session["messages"] = []
            self._session["title"] = None
            self._save_session_quiet()
        self.chat_panel.clear_chat()
        self.chat_panel.add_system_message("🤖 Chat cleared. Ready for new conversation!")
        self._refresh_session_list()

    # ------------------------------------------------------------------
    # Chat sessions
    # ------------------------------------------------------------------
    def _ensure_current_session(self, mode: str, workspace: str | None = None) -> dict:
        """Return the open session, creating/upgrading it lazily."""
        if self._session is None:
            self._session = self._store.create(mode, workspace)
        elif mode == "agent":
            self._session["mode"] = "agent"
            if workspace:
                self._session["workspace"] = workspace
        self._current_session_id = self._session["id"]
        return self._session

    def _save_session_quiet(self) -> None:
        """Persist the open session; failures surface as a system message."""
        if self._session is None:
            return
        try:
            self._store.save(self._session)
        except Exception as e:  # noqa: BLE001 - never crash chat on I/O errors
            logger.error("Failed to save session: %s", e)
            self.chat_panel.add_system_message("⚠️ Failed to save chat session")

    def _refresh_session_list(self) -> None:
        self.sidebar.set_sessions(self._store.list_sessions(), self._current_session_id)

    def _on_new_chat(self) -> None:
        """Start a fresh conversation; the previous one stays saved."""
        self._session = None
        self._current_session_id = None
        self.conversation_history.clear()
        self.chat_panel.clear_chat()
        self._refresh_session_list()

    def _on_session_selected(self, session_id: str) -> None:
        if session_id == self._current_session_id:
            return
        session = self._store.load(session_id)
        if session is None:
            return
        self._stop_running_work()
        self._save_session_quiet()
        self._open_session(session)

    def _on_session_rename(self, session_id: str) -> None:
        session = self._store.load(session_id)
        current_title = (session or {}).get("title") or ""
        title, ok = QInputDialog.getText(
            self, "Rename Chat", "Session title:", text=current_title
        )
        if not ok:
            return
        self._store.rename(session_id, title)
        if session_id == self._current_session_id and self._session is not None:
            self._session["title"] = title.strip() or None
        self._refresh_session_list()

    def _on_session_delete(self, session_id: str) -> None:
        # Sidebar already handles two-step inline confirmation with 3s
        # auto-cancel, so no additional QMessageBox is needed here.
        self._store.delete(session_id)
        if session_id == self._current_session_id:
            self._on_new_chat()
        else:
            self._refresh_session_list()

    def _stop_running_work(self) -> None:
        """Cancel any in-flight generation before switching sessions."""
        self._agent_service.stop()
        self._chat_service.stop()
        self.chat_panel.finish_streaming()
        self.chat_panel.agent_panel.finish_streaming()

    def _open_session(self, session: dict) -> None:
        """Load *session* into the UI (bubbles / agent transcript)."""
        self._session = session
        self._current_session_id = session["id"]
        messages = session.get("messages") or []
        self.conversation_history = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
        ]

        p = self.chat_panel
        p.clear_chat()
        agent_mode = session.get("mode") == "agent"
        p.set_agent_mode(agent_mode)
        p.show_agent_controls(agent_mode)
        p.set_agent_panel_visible(agent_mode)
        if agent_mode:
            workspace = session.get("workspace")
            if workspace:
                p.set_workspace(workspace)
            p.set_placeholder("Type your message to the agent...")
        else:
            p.set_placeholder("Type your message here...")

        target = p.agent_panel if agent_mode else p
        for msg in messages:
            role = msg.get("role")
            if role == "user":
                target.add_user_message(str(msg.get("content", "")))
            elif role == "assistant":
                target.add_ai_message(str(msg.get("content", "")))
            elif role == "tool":
                result = msg.get("tool_result")
                if isinstance(result, dict):
                    p.agent_panel.add_tool_card(result)

        self._refresh_session_list()

    def _restore_last_session(self) -> None:
        """Reopen the most recently updated session at startup."""
        for meta in self._store.list_sessions():
            if not meta.get("corrupt"):
                session = self._store.load(meta["id"])
                if session is not None:
                    self._open_session(session)
                return

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
            # Leave agent mode: return the display to the normal chat page.
            p.set_agent_panel_visible(False)
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

        self._ensure_current_session("agent", self.chat_panel.get_workspace())
        self._store.append_message(self._session, "user", text)
        self._save_session_quiet()
        self._refresh_session_list()

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
        if response and self._session is not None:
            self._store.append_message(self._session, "assistant", response)
            self._save_session_quiet()
            self._refresh_session_list()

    def _on_agent_cancelled(self) -> None:
        panel = self.chat_panel.agent_panel
        panel.finish_streaming()
        panel.mark_cancelled()
        panel.add_status("⏹ Agent run cancelled")
        self._save_session_quiet()
        self._refresh_session_list()

    def _on_agent_tool_executed(self, result: dict) -> None:
        self.chat_panel.agent_panel.add_tool_card(result)
        if self._session is not None and isinstance(result, dict):
            self._store.append_tool_result(self._session, result)

    def _on_agent_error(self, message: str) -> None:
        self.chat_panel.agent_panel.finish_streaming()
        self.chat_panel.agent_panel.add_status(f"❌ Error: {message}")
        self.chat_panel.set_agent_status("🟢 Ready")
        self._save_session_quiet()
        self._refresh_session_list()

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
        from ggufloader.widgets.feedback_dialog import FeedbackDialog
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
