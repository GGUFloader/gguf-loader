"""
AgentService - Qt bridge that runs :class:`AgentEngine` on a worker thread.

The signal surface intentionally mirrors the old ``SimpleAgent`` so the
UI layer can keep the same agent-mode logic while the engine itself is
pure and testable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from shiboken6 import isValid

from core.agent import AgentEngine, ToolRegistry
from core.llm.model_backend import ModelBackend
from core.llm.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class AgentWorker(QObject):
    """Executes one agent turn inside a QThread.

    Args are assigned as attributes before the thread starts; :meth:`process`
    is a zero-arg slot so Qt can invoke it across threads reliably.
    """

    response_generated = Signal(str)
    tool_executed = Signal(dict)
    error_occurred = Signal(str)
    processing_started = Signal()
    processing_finished = Signal()
    status_update = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.engine: Optional[AgentEngine] = None
        self.message: str = ""

    @Slot()
    def process(self) -> None:
        try:
            self.processing_started.emit()
            result = self.engine.process(
                self.message,
                on_status=lambda msg: self.status_update.emit(msg),
                on_tool=lambda res: self.tool_executed.emit(res),
            )
            self.response_generated.emit(result["response"])
        except Exception as e:  # noqa: BLE001
            logger.error("Agent worker error: %s", e)
            self.error_occurred.emit(str(e))
        finally:
            self.processing_finished.emit()


class AgentService(QObject):
    """Runs agent turns in the background and forwards events to the UI."""

    response_generated = Signal(str)
    tool_executed = Signal(dict)
    error_occurred = Signal(str)
    processing_started = Signal()
    processing_finished = Signal()
    status_update = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[AgentWorker] = None
        self._engine: Optional[AgentEngine] = None

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------
    def create_engine(self, backend: ModelBackend, workspace: str | Path) -> AgentEngine:
        """Build an AgentEngine bound to *backend* and *workspace*."""

        def llm(prompt: str, max_tokens: int = 2048, temperature: float = 0.1) -> str:
            return backend.generate(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                repeat_penalty=1.1,
                top_k=40,
                stop=PromptBuilder.stop_tokens(),
            )

        tools = ToolRegistry(Path(workspace))
        self._engine = AgentEngine(llm, Path(workspace), tools=tools)
        return self._engine

    @property
    def engine(self) -> Optional[AgentEngine]:
        return self._engine

    # ------------------------------------------------------------------
    # Turn lifecycle
    # ------------------------------------------------------------------
    def process_message(self, engine: AgentEngine, message: str) -> None:
        """Start processing *message* on a background thread."""
        self.stop()

        worker = AgentWorker()
        worker.engine = engine
        worker.message = message

        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.process)
        worker.response_generated.connect(self.response_generated.emit)
        worker.tool_executed.connect(self.tool_executed.emit)
        worker.error_occurred.connect(self.error_occurred.emit)
        worker.processing_started.connect(self.processing_started.emit)
        worker.processing_finished.connect(self.processing_finished.emit)
        worker.status_update.connect(self.status_update.emit)
        worker.processing_finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._clear_refs(thread, worker))

        self._worker = worker
        self._thread = thread
        thread.start()

    def _clear_refs(self, thread: QThread, worker: AgentWorker) -> None:
        """Drop references once a finished thread is gone (avoids stale handles)."""
        if self._thread is thread:
            self._thread = None
        if self._worker is worker:
            self._worker = None

    def stop(self) -> None:
        thread = self._thread
        if thread is not None and isValid(thread) and thread.isRunning():
            thread.quit()
            thread.wait(2000)
        self._worker = None
        self._thread = None
