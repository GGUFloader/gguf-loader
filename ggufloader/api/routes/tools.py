"""Tool routes - list and manage agent tools."""

from __future__ import annotations

import logging
from typing import List, Optional, Set

from fastapi import APIRouter
from pydantic import BaseModel

from ggufloader.api.deps import get_workspace

router = APIRouter()
logger = logging.getLogger(__name__)


class ToolToggleRequest(BaseModel):
    name: str
    active: bool


class ToolInfo(BaseModel):
    name: str
    label: str
    category: str
    risk: str
    active: bool


@router.get("")
async def list_tools() -> List[ToolInfo]:
    """List all available agent tools with their active state."""
    from pathlib import Path
    from ggufloader.core.agent.tool_manager import ToolManager

    workspace = Path(get_workspace()) if get_workspace() else Path(".")
    manager = ToolManager(workspace)
    tools = manager.get_all_tool_info()
    return [ToolInfo(**t) for t in tools]


@router.get("/active")
async def active_tools() -> List[str]:
    """Get list of active tool names."""
    from pathlib import Path
    from ggufloader.core.agent.tool_manager import ToolManager

    workspace = Path(get_workspace()) if get_workspace() else Path(".")
    manager = ToolManager(workspace)
    return sorted(manager.get_active_tools())


@router.post("/toggle")
async def toggle_tool(req: ToolToggleRequest) -> dict:
    """Enable or disable a tool."""
    from pathlib import Path
    from ggufloader.core.agent.tool_manager import ToolManager

    workspace = Path(get_workspace()) if get_workspace() else Path(".")
    manager = ToolManager(workspace)
    changed = manager.set_tool_active(req.name, req.active)
    return {"ok": changed, "active": sorted(manager.get_active_tools())}


@router.get("/stats")
async def tool_stats() -> dict:
    """Get tool usage statistics."""
    from pathlib import Path
    from ggufloader.core.agent.tool_manager import ToolManager

    workspace = Path(get_workspace()) if get_workspace() else Path(".")
    manager = ToolManager(workspace)
    all_info = manager.get_all_tool_info()
    active = sum(1 for t in all_info if t["active"])
    return {
        "total_tools": len(all_info),
        "active_tools": active,
        "inactive_tools": len(all_info) - active,
    }
