"""API Server addon — OpenAI-compatible local server with streaming.

Exposes the loaded GGUF model via http://127.0.0.1:{port}/v1/chat/completions
Supports streaming SSE (unlike GPT4All which rejects it).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from ggufloader.addons.api_server.server import make_server


class ApiServerController(QObject):
    started = Signal(int)  # port
    stopped = Signal()
    error = Signal(str)

    def __init__(self, get_backend, get_model_id, parent=None):
        super().__init__(parent)
        self._get_backend = get_backend
        self._get_model_id = get_model_id
        self._server = None
        self._thread: Optional[QThread] = None

    def is_running(self) -> bool:
        return self._server is not None

    def start(self, host: str = "127.0.0.1", port: int = 8080):
        if self.is_running():
            self.stop()
        try:
            self._server = make_server(host, port, self._get_backend, self._get_model_id)
            # Run serve_forever in a QThread
            self._thread = QThread(self)
            self._thread.started.connect(self._server.serve_forever)
            self._thread.start()
            self.started.emit(port)
        except OSError as e:
            self._server = None
            self.error.emit(f"Port {port} unavailable: {e}")
        except Exception as e:
            self._server = None
            self.error.emit(str(e))

    def stop(self):
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
        if self._thread is not None:
            try:
                self._thread.quit()
                self._thread.wait(1500)
            except Exception:
                pass
            self._thread = None
        self.stopped.emit()


def _find_main_window(widget):
    # Walk up parent chain
    w = widget
    visited = set()
    while w is not None and id(w) not in visited:
        visited.add(id(w))
        if hasattr(w, "model") or hasattr(w, "_model_service"):
            # Check it's MainWindow-like (has model_loaded signal etc.)
            return w
        try:
            w = w.parent()
        except Exception:
            break
        if w is None:
            break
    # Fallback scan top-level widgets
    try:
        from PySide6.QtWidgets import QApplication
        for tl in QApplication.topLevelWidgets():
            if hasattr(tl, "_model_service"):
                return tl
    except Exception:
        pass
    return widget


def register(parent=None) -> QWidget:
    """Addon entry point."""
    # Resolve main window for backend access
    main_win = _find_main_window(parent)

    def get_backend():
        try:
            svc = getattr(main_win, "_model_service", None)
            if svc is not None and getattr(svc, "is_loaded", False):
                return svc.backend
            # Fallback: direct model attribute
            m = getattr(main_win, "model", None)
            if m is not None:
                # Wrap callable model into backend-like interface
                return None
            return None
        except Exception:
            return None

    def get_model_id():
        try:
            svc = getattr(main_win, "_model_service", None)
            if svc and getattr(svc, "backend", None):
                return Path(svc.backend.model_path).name
            m = getattr(main_win, "model", None)
            if m and hasattr(m, "model_path"):
                return Path(m.model_path).name
        except Exception:
            pass
        return "gguf-model"

    controller = ApiServerController(get_backend, get_model_id)

    widget = QWidget(parent)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    title = QLabel("🔌 OpenAI-Compatible API Server")
    title.setObjectName("panelTitle")
    layout.addWidget(title)

    desc = QLabel("Exposes the loaded model at http://127.0.0.1:{port}/v1/chat/completions\n"
                  "Supports streaming (unlike GPT4All). Works with any OpenAI client.")
    desc.setWordWrap(True)
    desc.setObjectName("mutedLabel")
    layout.addWidget(desc)

    row = QHBoxLayout()
    row.addWidget(QLabel("Port:"))
    port_spin = QSpinBox()
    port_spin.setRange(1024, 65535)
    port_spin.setValue(8080)
    port_spin.setFixedWidth(90)
    row.addWidget(port_spin)
    row.addStretch(1)
    layout.addLayout(row)

    status = QLabel("● Stopped")
    status.setObjectName("mutedLabel")
    layout.addWidget(status)

    btn_row = QHBoxLayout()
    toggle_btn = QPushButton("▶ Start Server")
    toggle_btn.setObjectName("primaryButton")
    toggle_btn.setMinimumHeight(36)
    copy_btn = QPushButton("Copy curl example")
    copy_btn.setMinimumHeight(36)
    btn_row.addWidget(toggle_btn)
    btn_row.addWidget(copy_btn)
    layout.addLayout(btn_row)

    def update_status(running: bool, port: int = 8080):
        if running:
            status.setText(f"● Running on http://127.0.0.1:{port}")
            status.setProperty("state", "ok")
            toggle_btn.setText("⏹ Stop Server")
        else:
            status.setText("● Stopped")
            status.setProperty("state", "")
            toggle_btn.setText("▶ Start Server")
        status.style().unpolish(status)
        status.style().polish(status)

    def on_toggle():
        if controller.is_running():
            controller.stop()
        else:
            controller.start(port=port_spin.value())

    def on_copy():
        from PySide6.QtWidgets import QApplication
        port = port_spin.value()
        example = (
            f"curl http://127.0.0.1:{port}/v1/chat/completions \\\n"
            f"  -H \"Content-Type: application/json\" \\\n"
            f"  -d '{{\"model\": \"{get_model_id()}\", "
            "\"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}], \"stream\": true}}'"
        )
        QApplication.clipboard().setText(example)
        status.setText("📋 Copied example to clipboard")
        status.style().unpolish(status)
        status.style().polish(status)

    toggle_btn.clicked.connect(on_toggle)
    copy_btn.clicked.connect(on_copy)
    controller.started.connect(lambda p: update_status(True, p))
    controller.stopped.connect(lambda: update_status(False))
    controller.error.connect(lambda msg: status.setText(f"❌ {msg}"))

    # Store controller on widget to keep alive
    widget._api_controller = controller  # type: ignore

    layout.addStretch(1)
    return widget
