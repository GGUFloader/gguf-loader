"""Plugin routes - manage agent plugins."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def list_plugins() -> List[dict]:
    """List all installed plugins."""
    from pathlib import Path
    from ggufloader.api.deps import get_workspace
    from ggufloader.core.agent.plugin_manager import PluginManager

    workspace = Path(get_workspace()) if get_workspace() else Path(".")
    pm = PluginManager(workspace)
    loaded = pm.get_loaded()
    return [{"name": p, "status": "loaded", "enabled": True} for p in loaded]


@router.get("/stats")
async def plugin_stats() -> dict:
    """Get plugin statistics."""
    return {"total": 0, "loaded": 0, "failed": 0}


@router.post("/{name}/enable")
async def enable_plugin(name: str) -> dict:
    """Enable a plugin."""
    return {"name": name, "status": "enabled"}


@router.post("/{name}/disable")
async def disable_plugin(name: str) -> dict:
    """Disable a plugin."""
    return {"name": name, "status": "disabled"}
