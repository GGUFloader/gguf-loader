"""
ToolManager - Lightweight tool management for the file-assistant agent.

Only activates the tools the user needs. Heavy subsystems (audit, replay,
profiler, error patterns, self-improvement) are lazy-loaded only when their
respective sidebar plugin is enabled.

Default active tools: read_file, list_directory, search_files, glob
All other tools are disabled until the user enables them in settings.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .tool_registry import (
    ALL_TOOL_CLASSES,
    ToolRegistry,
    tool_content_for_context,
    validate_tool_call,
)

logger = logging.getLogger(__name__)

# Default active tools for the lightweight file-assistant
DEFAULT_ACTIVE_TOOLS: Set[str] = {
    "read_file",
    "list_directory",
    "search_files",
    "glob",
}

# Tools that are available but disabled by default
DISABLED_TOOLS: Set[str] = {
    "write_file",
    "edit_file",
    "run_command",
    "run_python",
    "git",
    "batch_execute",
    "python_interpreter",
    "move_file",
    "remember",
    "recall",
    "forget",
    "record_correction",
    "generate_agents_md",
    "export_session",
}

# Tool categories for the frontend plugin registry
TOOL_CATEGORIES = {
    "read_file": {"category": "core", "label": "Read File", "risk": "low"},
    "list_directory": {"category": "core", "label": "List Directory", "risk": "low"},
    "search_files": {"category": "core", "label": "Search Files", "risk": "low"},
    "glob": {"category": "core", "label": "Glob Find", "risk": "low"},
    "write_file": {"category": "dev", "label": "Write File", "risk": "medium"},
    "edit_file": {"category": "dev", "label": "Edit File", "risk": "medium"},
    "run_command": {"category": "dev", "label": "Run Command", "risk": "high"},
    "run_python": {"category": "dev", "label": "Run Python", "risk": "high"},
    "git": {"category": "dev", "label": "Git", "risk": "high"},
    "batch_execute": {"category": "dev", "label": "Batch Execute", "risk": "medium"},
    "python_interpreter": {"category": "dev", "label": "Python Sandbox", "risk": "low"},
    "move_file": {"category": "dev", "label": "Move File", "risk": "medium"},
    "remember": {"category": "agent", "label": "Remember", "risk": "low"},
    "recall": {"category": "agent", "label": "Recall Memory", "risk": "low"},
    "forget": {"category": "agent", "label": "Forget Memory", "risk": "low"},
    "record_correction": {"category": "agent", "label": "Record Correction", "risk": "low"},
    "generate_agents_md": {"category": "agent", "label": "Generate AGENTS.md", "risk": "low"},
    "export_session": {"category": "agent", "label": "Export Session", "risk": "low"},
}


class ToolManager:
    """Manages which tools are active and provides lazy subsystem access."""

    def __init__(self, workspace: Path, config_path: Optional[Path] = None) -> None:
        self.workspace = workspace
        self._config_path = config_path or (workspace / ".ggufloader-tools.json")
        self._active_tools: Set[str] = set()
        self._registry: Optional[ToolRegistry] = None
        self._lazy_subsystems: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load tool activation config from disk."""
        if self._config_path.exists():
            try:
                data = json.loads(self._config_path.read_text(encoding="utf-8"))
                self._active_tools = set(data.get("active_tools", []))
            except Exception:
                self._active_tools = set(DEFAULT_ACTIVE_TOOLS)
        else:
            self._active_tools = set(DEFAULT_ACTIVE_TOOLS)

        # Ensure at least the defaults are active
        self._active_tools.update(DEFAULT_ACTIVE_TOOLS)

    def _save_config(self) -> None:
        """Save tool activation config to disk."""
        try:
            data = {"active_tools": sorted(self._active_tools)}
            self._config_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Failed to save tool config: %s", e)

    def get_active_tools(self) -> Set[str]:
        """Return the set of active tool names."""
        return set(self._active_tools)

    def is_tool_active(self, name: str) -> bool:
        """Check if a specific tool is active."""
        return name in self._active_tools

    def set_tool_active(self, name: str, active: bool) -> bool:
        """Enable or disable a tool. Returns True if the state changed."""
        if active:
            if name in DISABLED_TOOLS or name in TOOL_CATEGORIES:
                self._active_tools.add(name)
                self._save_config()
                self._registry = None  # invalidate cache
                return True
            return False
        else:
            # Don't allow disabling default tools
            if name in DEFAULT_ACTIVE_TOOLS:
                return False
            if name in self._active_tools:
                self._active_tools.discard(name)
                self._save_config()
                self._registry = None
                return True
            return False

    def get_registry(self) -> ToolRegistry:
        """Get a ToolRegistry with only active tools registered."""
        if self._registry is None:
            self._registry = ToolRegistry(self.workspace, only=list(self._active_tools))
        return self._registry

    def get_all_tool_info(self) -> List[Dict[str, Any]]:
        """Get info about all tools (active and inactive) for the frontend."""
        result = []
        for name, cat in TOOL_CATEGORIES.items():
            result.append({
                "name": name,
                "label": cat["label"],
                "category": cat["category"],
                "risk": cat["risk"],
                "active": name in self._active_tools,
            })
        return result

    def get_lazy(self, name: str, factory):
        """Get a lazily-initialized subsystem. Only creates it on first access."""
        if name not in self._lazy_subsystems:
            self._lazy_subsystems[name] = factory()
        return self._lazy_subsystems[name]

    def is_subsystem_enabled(self, name: str) -> bool:
        """Check if a heavy subsystem should be active based on enabled plugins."""
        # These subsystems are only needed when dev/agent plugins are on
        ENABLED_BY_PLUGINS = {
            "audit": {"dev", "agent"},
            "replay": {"dev"},
            "profiler": {"dev"},
            "error_patterns": {"agent"},
            "self_improve": {"agent"},
            "cost": {"dev"},
            "health": {"dev"},
        }
        # For now, all are disabled in lightweight mode
        return False
