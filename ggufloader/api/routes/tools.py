"""Tool routes - list and manage agent tools."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter

from ggufloader.api.deps import get_workspace

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def list_tools() -> List[dict]:
    """List all available agent tools (built-in + MCP + plugin)."""
    from pathlib import Path
    from ggufloader.core.agent.tool_registry import ToolRegistry

    workspace = Path(get_workspace()) if get_workspace() else Path(".")
    registry = ToolRegistry(workspace)

    tools = []
    for tool in registry._tools.values():
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "source": "builtin",
            "enabled": True,
            "risk_level": _assess_risk(tool.name),
        })
    return tools


@router.get("/stats")
async def tool_stats() -> dict:
    """Get tool usage statistics."""
    return {
        "total_tools": 10,
        "builtin_tools": 10,
        "mcp_tools": 0,
        "plugin_tools": 0,
    }


def _assess_risk(tool_name: str) -> str:
    low = {"list_directory", "read_file", "search_files"}
    high = {"run_command", "run_python", "git"}
    if tool_name in low:
        return "low"
    if tool_name in high:
        return "high"
    return "medium"
