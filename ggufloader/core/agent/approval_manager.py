"""
ApprovalManager - Risk-based tool approval with batch support.

Pattern from: Aider ConfirmGroup + OpenHands security analysis.
Manages the approval workflow for agent tool calls with:
- Risk-based auto-approve (low-risk reads auto-approve)
- Batch approval (approve/deny all similar calls)
- Approval history and learning
- Configurable rules per tool
- Undo last approval
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ApprovalDecision(Enum):
    APPROVED = "approved"
    DENIED = "denied"
    AUTO_APPROVED = "auto_approved"
    SKIPPED = "skipped"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalRequest:
    """A single approval request."""

    def __init__(self, request_id: str, tool_name: str, params: Dict[str, Any],
                 risk: RiskLevel, description: str = "") -> None:
        self.request_id = request_id
        self.tool_name = tool_name
        self.params = params
        self.risk = risk
        self.description = description
        self.timestamp = time.time()
        self.decision: Optional[ApprovalDecision] = None
        self.decision_time: Optional[float] = None

    @property
    def duration_ms(self) -> int:
        if self.decision_time and self.timestamp:
            return int((self.decision_time - self.timestamp) * 1000)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.request_id,
            "tool": self.tool_name,
            "risk": self.risk.value,
            "description": self.description,
            "decision": self.decision.value if self.decision else None,
            "duration_ms": self.duration_ms,
        }


class ApprovalRule:
    """A rule for auto-approving or blocking tool calls."""

    def __init__(self, tool_pattern: str, decision: ApprovalDecision,
                 risk_level: RiskLevel = RiskLevel.LOW,
                 description: str = "") -> None:
        self.tool_pattern = tool_pattern  # exact match or prefix
        self.decision = decision
        self.risk_level = risk_level
        self.description = description

    def matches(self, tool_name: str) -> bool:
        """Check if this rule matches a tool name."""
        if self.tool_pattern == "*":
            return True
        if self.tool_pattern.endswith("*"):
            return tool_name.startswith(self.tool_pattern[:-1])
        return tool_name == self.tool_pattern


class ApprovalManager:
    """Manage tool approval requests with risk-based rules.

    Usage:
        mgr = ApprovalManager()

        # Set rules
        mgr.add_rule(ApprovalRule("read_file*", ApprovalDecision.AUTO_APPROVED))
        mgr.add_rule(ApprovalRule("run_command", ApprovalDecision.DENIED))

        # Request approval
        approved = mgr.request_approval("run_command", {"command": "ls"})

        # Batch mode
        mgr.set_batch_preference("all")  # auto-approve all
    """

    def __init__(self) -> None:
        self._rules: List[ApprovalRule] = []
        self._history: List[ApprovalRequest] = []
        self._batch_preference: Optional[ApprovalDecision] = None
        self._pending: List[ApprovalRequest] = []
        self._approval_handler: Optional[Callable[[ApprovalRequest], ApprovalDecision]] = None
        self._auto_approve_low_risk = True
        self._request_counter = 0
        self._lock = threading.Lock()

        # Default rules
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        """Set up default approval rules."""
        # Auto-approve read-only tools
        self.add_rule(ApprovalRule("list_directory", ApprovalDecision.AUTO_APPROVED,
                                   RiskLevel.LOW, "Read-only directory listing"))
        self.add_rule(ApprovalRule("read_file", ApprovalDecision.AUTO_APPROVED,
                                   RiskLevel.LOW, "Read-only file access"))
        self.add_rule(ApprovalRule("search_files", ApprovalDecision.AUTO_APPROVED,
                                   RiskLevel.LOW, "Read-only search"))
        self.add_rule(ApprovalRule("python_interpreter", ApprovalDecision.AUTO_APPROVED,
                                   RiskLevel.LOW, "Sandboxed Python execution"))

    def set_approval_handler(self, handler: Callable[[ApprovalRequest], ApprovalDecision]) -> None:
        """Set the handler for interactive approval requests."""
        self._approval_handler = handler

    def add_rule(self, rule: ApprovalRule) -> None:
        """Add an approval rule."""
        self._rules.append(rule)

    def remove_rule(self, tool_pattern: str) -> bool:
        """Remove a rule by tool pattern."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.tool_pattern != tool_pattern]
        return len(self._rules) < before

    def set_batch_preference(self, preference: str) -> None:
        """Set batch preference: 'all', 'skip', or None."""
        if preference == "all":
            self._batch_preference = ApprovalDecision.AUTO_APPROVED
        elif preference == "skip":
            self._batch_preference = ApprovalDecision.DENIED
        else:
            self._batch_preference = None

    def request_approval(self, tool_name: str, params: Dict[str, Any],
                         risk: str = "low", description: str = "") -> bool:
        """Request approval for a tool call.

        Returns True if approved, False if denied.
        """
        risk_level = RiskLevel(risk) if risk in ("low", "medium", "high") else RiskLevel.LOW

        # Create request
        with self._lock:
            self._request_counter += 1
            request = ApprovalRequest(
                request_id=f"req_{self._request_counter}",
                tool_name=tool_name,
                params=params,
                risk=risk_level,
                description=description,
            )

        # Check batch preference
        if self._batch_preference is not None:
            request.decision = self._batch_preference
            request.decision_time = time.time()
            self._history.append(request)
            logger.info("Batch %s: %s", self._batch_preference.value, tool_name)
            return self._batch_preference == ApprovalDecision.AUTO_APPROVED

        # Check rules
        for rule in self._rules:
            if rule.matches(tool_name):
                request.decision = rule.decision
                request.decision_time = time.time()
                self._history.append(request)
                if rule.decision != ApprovalDecision.AUTO_APPROVED:
                    logger.info("Rule %s for %s: %s", rule.tool_pattern, tool_name,
                               rule.decision.value)
                return rule.decision == ApprovalDecision.AUTO_APPROVED

        # Auto-approve low risk if enabled
        if self._auto_approve_low_risk and risk_level == RiskLevel.LOW:
            request.decision = ApprovalDecision.AUTO_APPROVED
            request.decision_time = time.time()
            self._history.append(request)
            return True

        # Interactive approval needed
        if self._approval_handler:
            decision = self._approval_handler(request)
            request.decision = decision
            request.decision_time = time.time()
            self._history.append(request)
            return decision == ApprovalDecision.APPROVED

        # Default: deny if no handler
        request.decision = ApprovalDecision.DENIED
        request.decision_time = time.time()
        self._history.append(request)
        return False

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent approval history."""
        return [r.to_dict() for r in self._history[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """Get approval statistics."""
        total = len(self._history)
        approved = sum(1 for r in self._history
                      if r.decision in (ApprovalDecision.APPROVED, ApprovalDecision.AUTO_APPROVED))
        denied = sum(1 for r in self._history
                    if r.decision == ApprovalDecision.DENIED)
        avg_time = 0
        if self._history:
            times = [r.duration_ms for r in self._history if r.duration_ms > 0]
            avg_time = sum(times) // len(times) if times else 0

        return {
            "total_requests": total,
            "approved": approved,
            "denied": denied,
            "approval_rate": round(approved / total * 100, 1) if total else 0,
            "avg_decision_time_ms": avg_time,
            "batch_preference": self._batch_preference.value if self._batch_preference else None,
            "rules_count": len(self._rules),
        }

    def undo_last(self) -> Optional[ApprovalRequest]:
        """Undo the last approval decision."""
        if self._history:
            last = self._history.pop()
            last.decision = None
            return last
        return None
