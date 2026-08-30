"""
WorkspaceManager - Manage multiple workspaces with independent configurations.

Each workspace has its own:
- Sessions and chat history
- Plugin configurations
- Memory and self-improvement data
- Model parameters and presets
- Agent checkpoints

Features:
- Create, switch, list, delete workspaces
- Independent settings per workspace
- Workspace-specific plugin directories
- Import/export workspace bundles
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

WORKSPACES_DIR = Path.home() / ".ggufloader" / "workspaces"
CONFIG_FILE = "workspace.json"
ACTIVE_WORKSPACE_KEY = "active_workspace"


class WorkspaceInfo:
    """Metadata for a workspace."""

    def __init__(
        self,
        id: str,
        name: str,
        path: str,
        created_at: float = 0.0,
        last_used: float = 0.0,
    ) -> None:
        self.id = id
        self.name = name
        self.path = path
        self.created_at = created_at or time.time()
        self.last_used = last_used or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "created_at": self.created_at,
            "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkspaceInfo":
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            path=data.get("path", ""),
            created_at=data.get("created_at", 0),
            last_used=data.get("last_used", 0),
        )


class WorkspaceManager:
    """Manage multiple workspaces."""

    def __init__(self) -> None:
        WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        self._registry_path = WORKSPACES_DIR / "registry.json"
        self._workspaces: Dict[str, WorkspaceInfo] = {}
        self._active_id: Optional[str] = None
        self._load_registry()

    @property
    def active(self) -> Optional[WorkspaceInfo]:
        return self._workspaces.get(self._active_id) if self._active_id else None

    @property
    def active_id(self) -> Optional[str]:
        return self._active_id

    def list_all(self) -> List[WorkspaceInfo]:
        return sorted(self._workspaces.values(), key=lambda w: w.last_used, reverse=True)

    def get(self, workspace_id: str) -> Optional[WorkspaceInfo]:
        return self._workspaces.get(workspace_id)

    def create(self, name: str, path: str = "") -> WorkspaceInfo:
        """Create a new workspace."""
        import hashlib
        ws_id = hashlib.sha256(f"{name}_{time.time()}".encode()).hexdigest()[:12]
        ws_path = path or str(WORKSPACES_DIR / ws_id)

        # Create workspace directory structure
        ws_dir = Path(ws_path)
        ws_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "sessions").mkdir(exist_ok=True)
        (ws_dir / "plugins").mkdir(exist_ok=True)
        (ws_dir / "templates").mkdir(exist_ok=True)
        (ws_dir / "memory").mkdir(exist_ok=True)

        ws = WorkspaceInfo(id=ws_id, name=name, path=ws_path)
        self._workspaces[ws_id] = ws
        self._save_registry()
        logger.info("Created workspace: %s (%s)", name, ws_id)
        return ws

    def switch_to(self, workspace_id: str) -> bool:
        """Switch to a different workspace."""
        if workspace_id not in self._workspaces:
            return False
        ws = self._workspaces[workspace_id]
        ws.last_used = time.time()
        self._active_id = workspace_id
        self._save_registry()
        logger.info("Switched to workspace: %s", ws.name)
        return True

    def delete(self, workspace_id: str) -> bool:
        """Delete a workspace."""
        if workspace_id not in self._workspaces:
            return False
        ws = self._workspaces.pop(workspace_id)
        if self._active_id == workspace_id:
            self._active_id = None
        self._save_registry()
        logger.info("Deleted workspace: %s", ws.name)
        return True

    def rename(self, workspace_id: str, new_name: str) -> bool:
        """Rename a workspace."""
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False
        ws.name = new_name
        self._save_registry()
        return True

    def get_plugins_dir(self, workspace_id: Optional[str] = None) -> Path:
        """Get the plugins directory for a workspace."""
        ws = self._workspaces.get(workspace_id or self._active_id)
        if ws:
            d = Path(ws.path) / "plugins"
            d.mkdir(parents=True, exist_ok=True)
            return d
        return WORKSPACES_DIR / "default_plugins"

    def get_sessions_dir(self, workspace_id: Optional[str] = None) -> Path:
        """Get the sessions directory for a workspace."""
        ws = self._workspaces.get(workspace_id or self._active_id)
        if ws:
            d = Path(ws.path) / "sessions"
            d.mkdir(parents=True, exist_ok=True)
            return d
        return WORKSPACES_DIR / "default_sessions"

    def get_settings(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Get workspace-specific settings."""
        ws = self._workspaces.get(workspace_id or self._active_id)
        if not ws:
            return {}
        settings_path = Path(ws.path) / CONFIG_FILE
        if settings_path.exists():
            try:
                return json.loads(settings_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save_settings(self, settings: Dict[str, Any], workspace_id: Optional[str] = None) -> None:
        """Save workspace-specific settings."""
        ws = self._workspaces.get(workspace_id or self._active_id)
        if not ws:
            return
        settings_path = Path(ws.path) / CONFIG_FILE
        settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_stats(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Get workspace statistics."""
        ws = self._workspaces.get(workspace_id or self._active_id)
        if not ws:
            return {}
        ws_path = Path(ws.path)
        session_count = len(list((ws_path / "sessions").glob("*.json"))) if (ws_path / "sessions").is_dir() else 0
        plugin_count = len(list((ws_path / "plugins").glob("*.*"))) if (ws_path / "plugins").is_dir() else 0
        template_count = len(list((ws_path / "templates").glob("*.json"))) if (ws_path / "templates").is_dir() else 0
        return {
            "sessions": session_count,
            "plugins": plugin_count,
            "templates": template_count,
        }

    def _load_registry(self) -> None:
        if self._registry_path.exists():
            try:
                data = json.loads(self._registry_path.read_text(encoding="utf-8"))
                self._active_id = data.get("active")
                for ws_data in data.get("workspaces", []):
                    ws = WorkspaceInfo.from_dict(ws_data)
                    self._workspaces[ws.id] = ws
            except Exception as e:
                logger.warning("Failed to load workspace registry: %s", e)

    def _save_registry(self) -> None:
        data = {
            "active": self._active_id,
            "workspaces": [ws.to_dict() for ws in self._workspaces.values()],
        }
        self._registry_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
