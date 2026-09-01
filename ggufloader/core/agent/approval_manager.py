"""
ApprovalManager — instance-based approval flow management.

Replaces the module-level ``_approval_events`` / ``_approval_results``
dicts in handler.py with a proper class that:
  - Supports concurrent approvals (keyed by call_id)
  - Is testable without globals
  - Cleanly separates from the transport layer

The agent thread calls :meth:`register` + :meth:`wait`, the frontend
calls :meth:`resolve`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class RiskLevel:
    """Risk levels for approval requests (backward compat)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalDecision:
    """Approval decision enum (backward compat)."""
    APPROVED = "approved"
    DENIED = "denied"
    PENDING = "pending"


class ApprovalManager:
    """Manages approval requests between the agent thread and the frontend.

    Usage::

        mgr = ApprovalManager()

        # Agent thread (sync):
        event = asyncio.Event()
        mgr.register("call_123", event)
        event.wait(timeout=120)
        approved = mgr.resolve("call_123", default=False)

        # Frontend (async):
        mgr.resolve("call_123", approved=True)
    """

    def __init__(self) -> None:
        self._events: Dict[str, asyncio.Event] = {}
        self._results: Dict[str, bool] = {}

    def register(self, call_id: str, event: asyncio.Event) -> None:
        """Register an approval request. Agent thread will block on *event*."""
        self._events[call_id] = event

    def resolve(self, call_id: str, approved: bool = False) -> bool:
        """Resolve an approval request. Returns the approved status.

        If the call_id was registered, signals the waiting agent thread.
        """
        self._results[call_id] = approved
        event = self._events.pop(call_id, None)
        if event:
            event.set()
        return approved

    def get_result(self, call_id: str, default: bool = False) -> bool:
        """Get the result of a resolved approval, or *default* if pending/unknown."""
        return self._results.pop(call_id, default)

    def pending_count(self) -> int:
        """Number of approval requests waiting for a response."""
        return len(self._events)

    def cancel_all(self) -> None:
        """Cancel all pending approvals (e.g. on agent stop)."""
        for call_id, event in self._events.items():
            self._results[call_id] = False
            event.set()
        self._events.clear()
