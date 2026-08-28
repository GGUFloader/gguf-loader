"""
Hooks - Lifecycle hooks for customizable agent behavior.

Pattern from: Claude Code hooks + Aider's auto-lint.
Allows users and plugins to register callbacks at key agent lifecycle points:

- before_message / after_message
- before_tool_call / after_tool_call
- before_step / after_step
- before_response / after_response
- on_error
- on_session_start / on_session_end

Hooks can:
- Modify data (pass-through, transform, or block)
- Log actions
- Trigger side effects (notifications, external services)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HookPoint(Enum):
    BEFORE_MESSAGE = "before_message"
    AFTER_MESSAGE = "after_message"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    BEFORE_STEP = "before_step"
    AFTER_STEP = "after_step"
    BEFORE_RESPONSE = "before_response"
    AFTER_RESPONSE = "after_response"
    ON_ERROR = "on_error"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"


class HookResult:
    """Result of a hook execution."""
    CONTINUE = "continue"    # Continue with default behavior
    BLOCK = "block"          # Block the action
    MODIFIED = "modified"    # Data was modified, use modified version


@dataclass
class HookRegistration:
    """A registered hook."""
    hook_id: str
    point: HookPoint
    fn: Callable
    priority: int = 0  # higher = runs first
    enabled: bool = True
    description: str = ""


class HookContext:
    """Context passed to hook functions."""

    def __init__(self, point: HookPoint, data: Dict[str, Any]) -> None:
        self.point = point
        self.data = data
        self.result = HookResult.CONTINUE
        self.modified_data: Optional[Dict[str, Any]] = None
        self.timestamp = time.time()

    def block(self, reason: str = "") -> None:
        """Block the action."""
        self.result = HookResult.BLOCK
        self.data["block_reason"] = reason

    def modify(self, new_data: Dict[str, Any]) -> None:
        """Modify the data."""
        self.result = HookResult.MODIFIED
        self.modified_data = new_data

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


class Hooks:
    """Lifecycle hooks manager.

    Usage:
        hooks = Hooks()

        # Register a hook
        hooks.register("log_tools", HookPoint.BEFORE_TOOL_CALL, my_logger)

        # Register a blocking hook
        hooks.register("block_dangerous", HookPoint.BEFORE_TOOL_CALL,
                       block_dangerous_commands, priority=10)

        # Execute hooks
        result = hooks.execute(HookPoint.BEFORE_TOOL_CALL, {"tool": "run_command", "params": {}})
        if result.result == HookResult.BLOCK:
            print("Blocked:", result.data.get("block_reason"))
    """

    def __init__(self) -> None:
        self._hooks: Dict[HookPoint, List[HookRegistration]] = {}
        self._execution_log: List[Dict[str, Any]] = []

    def register(self, hook_id: str, point: HookPoint, fn: Callable,
                 priority: int = 0, description: str = "") -> None:
        """Register a hook at a lifecycle point."""
        reg = HookRegistration(
            hook_id=hook_id, point=point, fn=fn,
            priority=priority, description=description,
        )
        if point not in self._hooks:
            self._hooks[point] = []
        self._hooks[point].append(reg)
        # Sort by priority (descending)
        self._hooks[point].sort(key=lambda r: -r.priority)

    def unregister(self, hook_id: str) -> bool:
        """Remove a hook by ID."""
        for point, hooks in self._hooks.items():
            before = len(hooks)
            self._hooks[point] = [h for h in hooks if h.hook_id != hook_id]
            if len(self._hooks[point]) < before:
                return True
        return False

    def enable(self, hook_id: str) -> bool:
        for hooks in self._hooks.values():
            for h in hooks:
                if h.hook_id == hook_id:
                    h.enabled = True
                    return True
        return False

    def disable(self, hook_id: str) -> bool:
        for hooks in self._hooks.values():
            for h in hooks:
                if h.hook_id == hook_id:
                    h.enabled = False
                    return True
        return False

    def execute(self, point: HookPoint, data: Dict[str, Any]) -> HookContext:
        """Execute all hooks at a lifecycle point.

        Returns HookContext with the final result (continue/block/modified).
        """
        context = HookContext(point, data)
        registrations = self._hooks.get(point, [])

        for reg in registrations:
            if not reg.enabled:
                continue
            try:
                reg.fn(context)
                self._execution_log.append({
                    "hook_id": reg.hook_id,
                    "point": point.value,
                    "result": context.result,
                    "timestamp": time.time(),
                })
                # If blocked, stop processing
                if context.result == HookResult.BLOCK:
                    break
            except Exception as e:
                logger.error("Hook '%s' error at %s: %s", reg.hook_id, point.value, e)
                self._execution_log.append({
                    "hook_id": reg.hook_id,
                    "point": point.value,
                    "result": "error",
                    "error": str(e),
                    "timestamp": time.time(),
                })

        return context

    def get_hooks_for(self, point: HookPoint) -> List[Dict[str, Any]]:
        """Get all registered hooks for a point."""
        return [
            {"id": h.hook_id, "priority": h.priority, "enabled": h.enabled,
             "description": h.description}
            for h in self._hooks.get(point, [])
        ]

    def get_execution_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._execution_log[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        total = sum(len(hooks) for hooks in self._hooks.values())
        return {
            "total_hooks": total,
            "by_point": {p.value: len(hooks) for p, hooks in self._hooks.items()},
            "executions": len(self._execution_log),
        }

    def clear(self) -> None:
        self._hooks.clear()
        self._execution_log.clear()
