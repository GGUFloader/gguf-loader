"""
AgentService - Qt bridge that runs :class:`GraphAgent` on a worker thread.

The agent engine is a LangGraph StateGraph (SQLite checkpointing,
streaming custom events, cooperative cancel). This service only shuttles
events between the graph and the UI: status/tool/token events become Qt
signals, and :meth:`stop` cancels the running turn cooperatively before
stopping the thread.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from shiboken6 import isValid

from ggufloader.core.agent import GraphAgent, ToolRegistry
from ggufloader.core.llm.model_backend import ModelBackend
from ggufloader.core.llm.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class ApprovalWaiter:
    """Thread-safe slot for the UI's answer to an approval request.

    The worker thread blocks on :meth:`wait` while the main thread shows
    the approval card; ``resolve(True/False)`` (from the card's buttons)
    releases it.
    """

    def __init__(self) -> None:
        self._event = threading.Event()
        self.result = False

    def resolved(self, timeout: float = 0.1) -> bool:
        """Block up to *timeout*; True once the UI has answered."""
        return self._event.wait(timeout)

    def resolve(self, approved: bool) -> None:
        self.result = bool(approved)
        self._event.set()


class AgentWorker(QObject):
    """Executes one agent turn inside a QThread.

    Args are assigned as attributes before the thread starts; :meth:`process`
    is a zero-arg slot so Qt can invoke it across threads reliably.
    """

    response_generated = Signal(str)
    tool_executed = Signal(dict)
    token_received = Signal(str)
    approval_requested = Signal(dict, object)
    cancelled = Signal()
    error_occurred = Signal(str)
    processing_started = Signal()
    processing_finished = Signal()
    status_update = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.engine: Optional[GraphAgent] = None
        self.message: str = ""
        self._cancel_requested = False

    @Slot()
    def process(self) -> None:
        try:
            self.processing_started.emit()
            result = self.engine.process(
                self.message,
                on_status=lambda msg: self.status_update.emit(msg),
                on_tool=lambda res: self.tool_executed.emit(res),
                on_token=lambda tok: self.token_received.emit(tok),
                on_approval=self._request_approval,
            )
            if result.get("cancelled"):
                self.cancelled.emit()
            else:
                self.response_generated.emit(result["response"])
        except Exception as e:  # noqa: BLE001
            logger.error("Agent worker error: %s", e)
            self.error_occurred.emit(str(e))
        finally:
            self.processing_finished.emit()

    def request_cancel(self) -> None:
        """Unblock any pending approval wait so the run can stop cooperatively."""
        self._cancel_requested = True

    def _request_approval(self, payload: dict) -> bool:
        """Ask the UI (main thread) for approval; blocks until answered."""
        waiter = ApprovalWaiter()
        self.approval_requested.emit(payload, waiter)
        while not waiter.resolved(0.1):
            if self._cancel_requested:
                return False
        return waiter.result


class AgentService(QObject):
    """Runs agent turns in the background and forwards events to the UI."""

    response_generated = Signal(str)
    tool_executed = Signal(dict)
    token_received = Signal(str)
    approval_requested = Signal(dict, object)
    cancelled = Signal()
    error_occurred = Signal(str)
    processing_started = Signal()
    processing_finished = Signal()
    status_update = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[AgentWorker] = None
        self._engine: Optional[GraphAgent] = None

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------
    def create_engine(self, backend: ModelBackend, workspace: str | Path) -> GraphAgent:
        """Build a GraphAgent bound to *backend* and *workspace*.

        The LLM callable streams tokens (``backend.generate_stream``); the
        graph consumes the chunk iterable and emits them as custom events.
        """
        self.stop()
        if self._engine is not None:
            self._engine.close()
            self._engine = None

        def llm(prompt: str, max_tokens: int = 2048, temperature: float = 0.1):
            return backend.generate_stream(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                repeat_penalty=1.1,
                top_k=40,
                stop=PromptBuilder.stop_tokens(),
            )

        tools = ToolRegistry(Path(workspace))
        self._engine = GraphAgent(llm, Path(workspace), tools=tools)
        return self._engine

    @property
    def engine(self) -> Optional[GraphAgent]:
        return self._engine

    # ------------------------------------------------------------------
    # Turn lifecycle
    # ------------------------------------------------------------------
    def process_message(self, engine: GraphAgent, message: str) -> None:
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
        worker.token_received.connect(self.token_received.emit)
        worker.approval_requested.connect(self.approval_requested.emit)
        worker.cancelled.connect(self.cancelled.emit)
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
        """Cancel the current run cooperatively, then stop its thread."""
        engine = self._engine
        if engine is not None:
            engine.cancel()
        worker = self._worker
        if worker is not None:
            worker.request_cancel()  # unblock a pending approval wait
        thread = self._thread
        if thread is not None and isValid(thread) and thread.isRunning():
            thread.quit()
            thread.wait(5000)
        self._worker = None
        self._thread = None
