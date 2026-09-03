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
from ggufloader.core.llm.prompt_builder import CHAT_STOP_TOKENS

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

        The router inspects the loaded model and selects per-family:
          * TokenCleaner (architecture-specific channel-marker stripping)
          * sampling parameters (temperature, top_k, top_p, repeat_penalty)
          * n_ctx, n_batch, n_threads, n_keep, flash_attn
          * system prompt tuned for that family

        The agent role then layers on top: lower temperature, tighter
        top_k, higher repeat_penalty for reliable JSON output.
        """
        from ggufloader.core.agent.model_profiles import get_profile
        from ggufloader.core.agent.token_cleaner import get_cleaner
        from ggufloader.core.router import ModelRole
        from ggufloader.api.deps import get_router

        self.stop()
        if self._engine is not None:
            self._engine.close()
            self._engine = None

        # ---- Router-based model inspection ----
        model_path = getattr(backend, "model_path", "")
        router_profile = None
        agent_role_config = None
        try:
            router = get_router()
            router_profile = router.inspect(model_path)
            agent_role_config = router.route(router_profile, ModelRole.AGENT)
        except Exception as e:  # noqa: BLE001 - router must never block agent
            logger.warning("ModelRouter inspect failed for %s: %s", model_path, e)

        # ---- Sampling params from the role config (router), with safe fallbacks ----
        temperature = 0.1
        top_p = 0.9
        top_k = 40
        repeat_penalty = 1.1
        max_tokens_default = 4096
        if agent_role_config is not None:
            temperature = agent_role_config.temperature
            top_p = agent_role_config.top_p
            top_k = agent_role_config.top_k
            repeat_penalty = agent_role_config.repeat_penalty
            max_tokens_default = agent_role_config.max_tokens

        def llm(prompt: str, max_tokens: int = max_tokens_default, temperature: float = temperature):
            # Template-aware single-turn chat call: the agent's raw prompt
            # is delivered as one user message so llama.cpp wraps it in the
            # model's native template (better instruction adherence than a
            # bare completion). No text stops - they hurt the strict JSON
            # protocol output.
            return backend.chat_stream(
                [{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repeat_penalty=repeat_penalty,
                stop=CHAT_STOP_TOKENS,
            )

        # ---- Per-family static profile (the lightweight agent profile) ----
        profile = get_profile(
            model_path,
            n_ctx_train=getattr(backend, "n_ctx_train", 0) or 0,
        )
        # Override max_tokens from the family profile if router didn't supply one
        if agent_role_config is None:
            max_tokens_default = profile.max_tokens

        # ---- Per-architecture TokenCleaner ----
        architecture = (router_profile.architecture if router_profile else "") or ""
        cleaner = get_cleaner(architecture)

        # ---- Per-family system prompt (optional override) ----
        family_system_prompt = None
        if agent_role_config is not None and agent_role_config.system_prompt:
            family_system_prompt = agent_role_config.system_prompt

        n_ctx_val = getattr(backend, "n_ctx", None) or profile.n_ctx_target
        tools = ToolRegistry(Path(workspace))
        self._engine = GraphAgent(
            llm,
            Path(workspace),
            tools=tools,
            max_tokens=max_tokens_default,
            max_steps=profile.max_steps,
            json_retries=profile.json_retries,
            n_ctx=n_ctx_val,
            max_directive_rounds=3,
            cleaner=cleaner,
            system_prompt=family_system_prompt,
        )
        if n_ctx_val:
            self._engine._context_budget.set_budget(n_ctx_val)
        if hasattr(backend, "count_tokens"):
            self._engine._context_budget.set_tokenizer(backend.count_tokens)
        logger.info(
            "Agent engine created: arch=%s family=%s temp=%.2f top_p=%.2f top_k=%d "
            "repeat_penalty=%.2f max_tokens=%d max_steps=%d cleaner=%s",
            architecture or "?",
            router_profile.family if router_profile else "?",
            temperature, top_p, top_k, repeat_penalty,
            max_tokens_default, profile.max_steps,
            type(cleaner).__name__,
        )
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
