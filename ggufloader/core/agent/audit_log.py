"""
AuditLog - Full traceability log for agent actions.

Pattern from: SWE-agent trajectory + OpenHands event stream.
Records every significant agent action in a structured log:
- Tool calls and results
- LLM requests and responses
- User messages
- Approval decisions
- Errors and retries
- Session lifecycle events

The audit log enables:
1. Debugging: What happened and why
2. Replay: Re-execute a session step by step
3. Analytics: Performance metrics per action type
4. Compliance: Full audit trail for sensitive operations
"""

from __future__ import annotations

import json
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    # Lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    # User
    USER_MESSAGE = "user_message"
    # Agent
    AGENT_STEP = "agent_step"
    AGENT_REASONING = "agent_reasoning"
    AGENT_ANSWER = "agent_answer"
    # Tools
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    # LLM
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    LLM_ERROR = "llm_error"
    # Approval
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_DECISION = "approval_decision"
    # System
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    RETRY = "retry"
    COMPACT = "compact"


class AuditEntry:
    """A single audit log entry."""

    def __init__(self, event_type: EventType, data: Dict[str, Any],
                 timestamp: float = None) -> None:
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or time.time()
        self.session_id: Optional[str] = None
        self.step: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "type": self.event_type.value,
            "timestamp": self.timestamp,
            "data": self.data,
        }
        if self.session_id:
            d["session_id"] = self.session_id
        if self.step is not None:
            d["step"] = self.step
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        entry = cls(
            event_type=EventType(data.get("type", "info")),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", 0),
        )
        entry.session_id = data.get("session_id")
        entry.step = data.get("step")
        return entry


class AuditLog:
    """Structured audit log for agent actions.

    Usage:
        log = AuditLog(workspace_path)

        # Record events
        log.log(EventType.TOOL_CALL, {"tool": "read_file", "path": "foo.py"})
        log.log(EventType.LLM_REQUEST, {"tokens": 500})

        # Query
        entries = log.query(event_type=EventType.TOOL_CALL)
        entries = log.query(since=time.time() - 3600)

        # Export
        log.export_json("audit_export.json")
    """

    def __init__(self, workspace: Path = None) -> None:
        self._workspace = workspace
        self._entries: List[AuditEntry] = []
        self._session_id: Optional[str] = None
        self._current_step = 0
        self._max_entries = 5000

    def set_session(self, session_id: str) -> None:
        """Set the current session ID for all new entries."""
        self._session_id = session_id
        self._current_step = 0
        self.log(EventType.SESSION_START, {"session_id": session_id})

    def log(self, event_type: EventType, data: Dict[str, Any]) -> AuditEntry:
        """Record an audit event."""
        entry = AuditEntry(event_type, data)
        entry.session_id = self._session_id
        entry.step = self._current_step

        self._entries.append(entry)

        # Trim old entries
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

        return entry

    def step(self) -> int:
        """Increment and return the current step number."""
        self._current_step += 1
        return self._current_step

    def log_tool_call(self, tool: str, params: Dict[str, Any]) -> AuditEntry:
        """Convenience: log a tool call."""
        return self.log(EventType.TOOL_CALL, {
            "tool": tool,
            "params": params,
        })

    def log_tool_result(self, tool: str, status: str, result: Any = None,
                        error: str = None, duration_ms: int = 0) -> AuditEntry:
        """Convenience: log a tool result."""
        data = {"tool": tool, "status": status, "duration_ms": duration_ms}
        if error:
            data["error"] = error
        if result:
            data["result"] = str(result)[:500]
        event = EventType.TOOL_ERROR if status == "error" else EventType.TOOL_RESULT
        return self.log(event, data)

    def log_llm_call(self, prompt_tokens: int = 0, completion_tokens: int = 0,
                     latency_ms: int = 0) -> AuditEntry:
        """Convenience: log an LLM request/response."""
        return self.log(EventType.LLM_REQUEST, {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "latency_ms": latency_ms,
        })

    def log_approval(self, tool: str, decision: str, risk: str = "low") -> AuditEntry:
        """Convenience: log an approval decision."""
        return self.log(EventType.APPROVAL_DECISION, {
            "tool": tool,
            "decision": decision,
            "risk": risk,
        })

    def log_error(self, error: str, context: str = "") -> AuditEntry:
        """Convenience: log an error."""
        return self.log(EventType.ERROR, {"error": error, "context": context})

    def query(self, event_type: EventType = None, since: float = None,
              limit: int = 100) -> List[AuditEntry]:
        """Query audit entries."""
        results = self._entries
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if since:
            results = [e for e in results if e.timestamp >= since]
        return results[-limit:]

    def get_tool_stats(self) -> Dict[str, Any]:
        """Get statistics about tool usage."""
        tool_calls = [e for e in self._entries if e.event_type == EventType.TOOL_CALL]
        tool_results = [e for e in self._entries if e.event_type in (EventType.TOOL_RESULT, EventType.TOOL_ERROR)]

        by_tool: Dict[str, Dict[str, int]] = {}
        for entry in tool_results:
            tool = entry.data.get("tool", "unknown")
            status = entry.data.get("status", "unknown")
            if tool not in by_tool:
                by_tool[tool] = {"success": 0, "error": 0}
            by_tool[tool][status] = by_tool[tool].get(status, 0) + 1

        return {
            "total_calls": len(tool_calls),
            "total_results": len(tool_results),
            "by_tool": by_tool,
        }

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of the current session."""
        session_entries = [
            e for e in self._entries if e.session_id == self._session_id
        ]
        return {
            "session_id": self._session_id,
            "total_events": len(session_entries),
            "steps": self._current_step,
            "tool_stats": self.get_tool_stats(),
            "errors": sum(1 for e in session_entries if e.event_type == EventType.ERROR),
            "retries": sum(1 for e in session_entries if e.event_type == EventType.RETRY),
        }

    def export_json(self, filepath: str = None) -> str:
        """Export the audit log as JSON."""
        data = [e.to_dict() for e in self._entries]
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        if filepath and self._workspace:
            path = self._workspace / filepath
            path.write_text(json_str, encoding="utf-8")
        return json_str

    def load_from_json(self, filepath: str) -> int:
        """Load audit entries from a JSON file."""
        if self._workspace:
            path = self._workspace / filepath
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    self._entries.extend(AuditEntry.from_dict(d) for d in data)
                    return len(data)
                except Exception as e:
                    logger.error("Failed to load audit log: %s", e)
        return 0

    def clear(self) -> None:
        self._entries.clear()
        self._current_step = 0
