"""
ConfigManager - Unified configuration for the entire agent system.

Pattern from: Aider's settings.py + Claude Code's CLAUDE.md config.
Consolidates all agent configuration into a single validated source:
- Agent behavior (max steps, temperature, retries)
- Tool permissions and blocklists
- UI preferences
- Plugin settings
- MCP server configs
- Feature toggles

Supports:
- JSON config files (project-level and global)
- Environment variable overrides
- Runtime validation
- Migration from older config versions
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Config file locations (search order)
CONFIG_FILES = [
    ".ggufloader.json",           # project-level
    ".ggufloader/config.json",    # project-level (subdir)
]

GLOBAL_CONFIG = Path.home() / ".ggufloader" / "config.json"

# Current config version
CONFIG_VERSION = 2

# Default values
DEFAULTS = {
    "version": CONFIG_VERSION,
    "agent": {
        "max_steps": 8,
        "max_tokens": 2048,
        "temperature": 0.1,
        "json_retries": 2,
        "max_reflections": 2,
        "reflection_enabled": True,
        "auto_commit": False,
        "auto_test": False,
        "auto_verify": True,
        "preset": "full_stack",
    },
    "tools": {
        "blocked_commands": [
            "rm -rf /", "sudo", "git push --force",
            "format", "mkfs", "dd if=",
        ],
        "blocked_tools": [],
        "auto_approve_read": True,
        "auto_approve_write": False,
        "auto_approve_command": False,
    },
    "context": {
        "budget_tokens": 8192,
        "system_prompt_tokens": 500,
        "compaction_threshold": 0.8,
        "max_history_messages": 50,
    },
    "ui": {
        "show_reasoning": True,
        "show_tool_details": True,
        "show_risk_badges": True,
        "show_token_count": True,
        "syntax_highlighting": True,
        "dark_mode": False,
        "font_size": 14,
    },
    "mcp": {
        "servers": {},
    },
    "plugins": {
        "enabled": True,
        "auto_discover": True,
        "custom_dirs": [],
    },
    "memory": {
        "enabled": True,
        "max_entries": 200,
        "auto_learn": True,
    },
    "knowledge": {
        "enabled": True,
        "auto_populate": True,
        "max_context_chars": 3000,
    },
    "health": {
        "enabled": True,
        "monitor_interval": 5,
        "alert_cpu_percent": 90,
        "alert_memory_percent": 85,
    },
    "audit": {
        "enabled": True,
        "max_entries": 5000,
        "export_on_session_end": False,
    },
    "self_improve": {
        "enabled": True,
        "max_corrections": 200,
        "advice_enabled": True,
    },
    "file_watcher": {
        "enabled": False,
        "poll_interval": 2.0,
        "ignore_patterns": [],
    },
    "session": {
        "auto_save": True,
        "auto_export": False,
        "max_checkpoints": 20,
    },
}


@dataclass
class AgentConfig:
    """Typed configuration for the agent system."""
    # Agent behavior
    max_steps: int = 8
    max_tokens: int = 2048
    temperature: float = 0.1
    json_retries: int = 2
    max_reflections: int = 2
    reflection_enabled: bool = True
    auto_commit: bool = False
    auto_test: bool = False
    auto_verify: bool = True
    preset: str = "full_stack"

    # Tools
    blocked_commands: List[str] = field(default_factory=lambda: [
        "rm -rf /", "sudo", "git push --force",
    ])
    blocked_tools: List[str] = field(default_factory=list)
    auto_approve_read: bool = True
    auto_approve_write: bool = False
    auto_approve_command: bool = False

    # Context
    budget_tokens: int = 8192
    system_prompt_tokens: int = 500

    # UI
    show_reasoning: bool = True
    show_tool_details: bool = True
    show_risk_badges: bool = True
    show_token_count: bool = True
    syntax_highlighting: bool = True
    dark_mode: bool = False
    font_size: int = 14

    # Feature toggles
    mcp_enabled: bool = False
    plugins_enabled: bool = True
    memory_enabled: bool = True
    knowledge_enabled: bool = True
    health_enabled: bool = True
    audit_enabled: bool = True
    self_improve_enabled: bool = True
    file_watcher_enabled: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        """Create config from a nested dict (from JSON)."""
        flat = {}
        for section_name, section in data.items():
            if isinstance(section, dict):
                for key, value in section.items():
                    flat[key] = value
            elif section_name in cls.__dataclass_fields__:
                flat[section_name] = section

        # Apply environment overrides
        env_overrides = _env_overrides()
        flat.update(env_overrides)

        # Filter to known fields
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in flat.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to nested dict (for JSON)."""
        return {
            "agent": {
                "max_steps": self.max_steps,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "json_retries": self.json_retries,
                "max_reflections": self.max_reflections,
                "reflection_enabled": self.reflection_enabled,
                "auto_commit": self.auto_commit,
                "auto_test": self.auto_test,
                "auto_verify": self.auto_verify,
                "preset": self.preset,
            },
            "tools": {
                "blocked_commands": self.blocked_commands,
                "blocked_tools": self.blocked_tools,
                "auto_approve_read": self.auto_approve_read,
                "auto_approve_write": self.auto_approve_write,
                "auto_approve_command": self.auto_approve_command,
            },
            "context": {
                "budget_tokens": self.budget_tokens,
                "system_prompt_tokens": self.system_prompt_tokens,
            },
            "ui": {
                "show_reasoning": self.show_reasoning,
                "show_tool_details": self.show_tool_details,
                "show_risk_badges": self.show_risk_badges,
                "show_token_count": self.show_token_count,
                "syntax_highlighting": self.syntax_highlighting,
                "dark_mode": self.dark_mode,
                "font_size": self.font_size,
            },
            "features": {
                "mcp_enabled": self.mcp_enabled,
                "plugins_enabled": self.plugins_enabled,
                "memory_enabled": self.memory_enabled,
                "knowledge_enabled": self.knowledge_enabled,
                "health_enabled": self.health_enabled,
                "audit_enabled": self.audit_enabled,
                "self_improve_enabled": self.self_improve_enabled,
                "file_watcher_enabled": self.file_watcher_enabled,
            },
        }


class ConfigManager:
    """Unified configuration manager.

    Loads config from (in priority order):
    1. Environment variables (GGUF_AGENT_*)
    2. Project-level .ggufloader.json
    3. Global ~/.ggufloader/config.json
    4. Built-in defaults
    """

    def __init__(self, workspace: Path = None) -> None:
        self.workspace = workspace
        self._config: Optional[AgentConfig] = None
        self._raw: Dict[str, Any] = {}
        self._sources: List[str] = []

    def load(self) -> AgentConfig:
        """Load configuration from all sources."""
        merged = dict(DEFAULTS)

        # Layer 1: Global config
        if GLOBAL_CONFIG.exists():
            try:
                global_data = json.loads(GLOBAL_CONFIG.read_text(encoding="utf-8"))
                merged = _deep_merge(merged, global_data)
                self._sources.append(str(GLOBAL_CONFIG))
            except Exception as e:
                logger.warning("Failed to load global config: %s", e)

        # Layer 2: Project-level config
        if self.workspace:
            for config_name in CONFIG_FILES:
                config_path = self.workspace / config_name
                if config_path.exists():
                    try:
                        project_data = json.loads(config_path.read_text(encoding="utf-8"))
                        merged = _deep_merge(merged, project_data)
                        self._sources.append(str(config_path))
                        break
                    except Exception as e:
                        logger.warning("Failed to load %s: %s", config_path, e)

        self._raw = merged
        self._config = AgentConfig.from_dict(merged)
        return self._config

    @property
    def config(self) -> AgentConfig:
        if self._config is None:
            self.load()
        return self._config

    def save(self, scope: str = "project") -> bool:
        """Save current config.

        Args:
            scope: "project" saves to .ggufloader.json, "global" saves to ~/.ggufloader/
        """
        if self._config is None:
            return False

        data = self._config.to_dict()
        data["version"] = CONFIG_VERSION

        try:
            if scope == "global":
                GLOBAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
                path = GLOBAL_CONFIG
            else:
                if self.workspace is None:
                    return False
                path = self.workspace / ".ggufloader.json"

            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Config saved to %s", path)
            return True
        except Exception as e:
            logger.error("Failed to save config: %s", e)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dotted key (e.g., 'agent.max_steps')."""
        parts = key.split(".")
        value = self._raw
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        """Set a config value by dotted key."""
        parts = key.split(".")
        target = self._raw
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
        self._config = AgentConfig.from_dict(self._raw)

    def validate(self) -> List[str]:
        """Validate current config. Returns list of issues."""
        issues = []
        cfg = self.config

        if cfg.max_steps < 1 or cfg.max_steps > 100:
            issues.append("agent.max_steps must be 1-100")
        if cfg.temperature < 0 or cfg.temperature > 2:
            issues.append("agent.temperature must be 0-2")
        if cfg.max_tokens < 256 or cfg.max_tokens > 128000:
            issues.append("agent.max_tokens must be 256-128000")
        if cfg.budget_tokens < 1024:
            issues.append("context.budget_tokens must be >= 1024")
        if cfg.font_size < 8 or cfg.font_size > 48:
            issues.append("ui.font_size must be 8-48")

        return issues

    def get_sources(self) -> List[str]:
        """Return list of config files that were loaded."""
        return list(self._sources)

    def reset_to_defaults(self) -> AgentConfig:
        """Reset all config to built-in defaults."""
        self._raw = dict(DEFAULTS)
        self._config = AgentConfig.from_dict(DEFAULTS)
        self._sources.clear()
        return self._config


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dicts, with override taking priority."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _env_overrides() -> Dict[str, Any]:
    """Read config overrides from environment variables.

    GGUF_AGENT_MAX_STEPS=12 → agent.max_steps = 12
    GGUF_AGENT_TEMPERATURE=0.5 → agent.temperature = 0.5
    """
    overrides = {}
    prefix = "GGUF_AGENT_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        config_key = key[len(prefix):].lower()
        # Convert to nested structure
        if config_key in ("max_steps", "max_tokens", "json_retries", "max_reflections",
                          "font_size", "budget_tokens", "system_prompt_tokens"):
            try:
                overrides[config_key] = int(value)
            except ValueError:
                pass
        elif config_key in ("temperature", "compaction_threshold", "poll_interval"):
            try:
                overrides[config_key] = float(value)
            except ValueError:
                pass
        elif config_key in ("reflection_enabled", "auto_commit", "auto_test",
                            "auto_verify", "show_reasoning", "dark_mode",
                            "mcp_enabled", "plugins_enabled", "memory_enabled"):
            overrides[config_key] = value.lower() in ("true", "1", "yes")
    return overrides
