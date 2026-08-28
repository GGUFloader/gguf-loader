"""
Capabilities - Dynamic capability registry for the agent system.

Pattern from: Pydantic AI Harness capabilities + OpenHands action space.
Every agent feature is registered as a capability with:
- Name and description
- Dependencies (what it needs)
- Status (enabled/disabled/unavailable)
- Health check

The capabilities registry enables:
1. Dynamic feature toggling at runtime
2. Dependency resolution
3. Feature discovery for the UI
4. Health monitoring per capability
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CapStatus(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class Capability:
    """A single agent capability."""

    def __init__(self, name: str, description: str,
                 dependencies: List[str] = None,
                 health_check: Callable[[], bool] = None) -> None:
        self.name = name
        self.description = description
        self.dependencies = dependencies or []
        self.health_check = health_check
        self.status = CapStatus.ENABLED
        self.error: Optional[str] = None

    def check_health(self) -> bool:
        """Run the health check if available."""
        if self.health_check is None:
            return True
        try:
            return self.health_check()
        except Exception as e:
            self.status = CapStatus.ERROR
            self.error = str(e)
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "error": self.error,
        }


class CapabilitiesRegistry:
    """Dynamic capability registry for the agent system.

    Usage:
        caps = CapabilitiesRegistry()
        caps.register("memory", "Persistent memory", [])
        caps.register("knowledge", "Knowledge base", ["memory"])
        caps.disable("file_watcher")

        # Check if a capability is available
        if caps.is_enabled("knowledge"):
            ...
    """

    def __init__(self) -> None:
        self._capabilities: Dict[str, Capability] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register all built-in capabilities."""
        # Core capabilities
        self.register("agent_engine", "Multi-step agent loop", [])
        self.register("tool_registry", "Sandboxed filesystem tools", [])
        self.register("model_loading", "GGUF model loading", [])

        # Phase 5
        self.register("memory", "Persistent memory across sessions", [])
        self.register("knowledge", "Project knowledge base", [])
        self.register("context_budget", "Context window management", ["memory"])
        self.register("semantic_search", "Advanced file search", ["tool_registry"])
        self.register("plugins", "Custom tool plugins", ["tool_registry"])

        # Phase 6
        self.register("retry", "Auto-retry with backoff", [])
        self.register("checkpoints", "File backup and undo", ["tool_registry"])
        self.register("stream_handler", "Streaming response repair", [])
        self.register("health_monitor", "System diagnostics", [])

        # Phase 7
        self.register("auto_commit", "Auto git commits", ["tool_registry"])
        self.register("auto_test", "Auto test runner", ["tool_registry"])
        self.register("agents_md", "AGENTS.md generation", [])
        self.register("cost_estimator", "Token cost tracking", [])

        # Phase 8
        self.register("presets", "Agent mode presets", ["agent_engine"])
        self.register("file_watcher", "Workspace file monitoring", [])
        self.register("session_export", "Session import/export", [])
        self.register("workspace_analytics", "Code metrics", [])

        # Phase 9
        self.register("parallel", "Multi-agent parallel execution", ["agent_engine"])
        self.register("approval", "Risk-based tool approval", ["agent_engine"])
        self.register("structured_output", "JSON schema validation", [])

        # Phase 10
        self.register("mcp", "MCP protocol client", ["tool_registry"])
        self.register("audit", "Full audit trail", [])
        self.register("self_improve", "Learn from corrections", ["memory"])

    def register(self, name: str, description: str,
                 dependencies: List[str] = None,
                 health_check: Callable[[], bool] = None) -> None:
        """Register a capability."""
        self._capabilities[name] = Capability(
            name, description, dependencies, health_check,
        )

    def enable(self, name: str) -> bool:
        """Enable a capability."""
        cap = self._capabilities.get(name)
        if cap is None:
            return False

        # Check dependencies
        for dep in cap.dependencies:
            dep_cap = self._capabilities.get(dep)
            if dep_cap and dep_cap.status != CapStatus.ENABLED:
                logger.warning("Cannot enable '%s': dependency '%s' is not enabled", name, dep)
                return False

        cap.status = CapStatus.ENABLED
        cap.error = None
        return True

    def disable(self, name: str) -> bool:
        """Disable a capability."""
        cap = self._capabilities.get(name)
        if cap is None:
            return False

        # Check if anything depends on this
        for other in self._capabilities.values():
            if name in other.dependencies and other.status == CapStatus.ENABLED:
                logger.warning("Cannot disable '%s': '%s' depends on it", name, other.name)
                return False

        cap.status = CapStatus.DISABLED
        return True

    def is_enabled(self, name: str) -> bool:
        """Check if a capability is enabled."""
        cap = self._capabilities.get(name)
        return cap is not None and cap.status == CapStatus.ENABLED

    def get(self, name: str) -> Optional[Capability]:
        return self._capabilities.get(name)

    def list_all(self) -> List[Dict[str, Any]]:
        """List all capabilities."""
        return [cap.to_dict() for cap in self._capabilities.values()]

    def list_enabled(self) -> List[str]:
        """List enabled capability names."""
        return [name for name, cap in self._capabilities.items()
                if cap.status == CapStatus.ENABLED]

    def list_disabled(self) -> List[str]:
        """List disabled capability names."""
        return [name for name, cap in self._capabilities.items()
                if cap.status == CapStatus.DISABLED]

    def health_check(self) -> Dict[str, bool]:
        """Run health checks on all capabilities."""
        results = {}
        for name, cap in self._capabilities.items():
            if cap.status == CapStatus.ENABLED:
                results[name] = cap.check_health()
            else:
                results[name] = False
        return results

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all capabilities."""
        enabled = sum(1 for c in self._capabilities.values() if c.status == CapStatus.ENABLED)
        disabled = sum(1 for c in self._capabilities.values() if c.status == CapStatus.DISABLED)
        errors = sum(1 for c in self._capabilities.values() if c.status == CapStatus.ERROR)
        return {
            "total": len(self._capabilities),
            "enabled": enabled,
            "disabled": disabled,
            "errors": errors,
        }
