"""MCP routes - manage MCP server connections and tools."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_workspace

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory MCP server configs (persisted via config_manager in production)
_mcp_servers: dict = {}


class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: List[str] = []
    env: dict = {}


@router.get("/servers")
async def list_mcp_servers() -> List[dict]:
    """List all configured MCP servers."""
    results = []
    for name, cfg in _mcp_servers.items():
        results.append({
            "name": name,
            "command": cfg.get("command", ""),
            "args": cfg.get("args", []),
            "status": "configured",
            "tools_count": 0,
        })
    return results


@router.post("/servers")
async def add_mcp_server(req: MCPServerConfig) -> dict:
    """Add a new MCP server configuration."""
    _mcp_servers[req.name] = {
        "command": req.command,
        "args": req.args,
        "env": req.env,
    }
    return {"status": "added", "name": req.name}


@router.delete("/servers/{name}")
async def remove_mcp_server(name: str) -> dict:
    """Remove an MCP server configuration."""
    if name not in _mcp_servers:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    del _mcp_servers[name]
    return {"status": "removed", "name": name}


@router.post("/servers/{name}/connect")
async def connect_mcp_server(name: str) -> dict:
    """Connect to an MCP server and discover its tools."""
    if name not in _mcp_servers:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    # In production, this would spawn the MCP process and do JSON-RPC
    return {"status": "connected", "name": name, "tools": []}


@router.post("/servers/{name}/disconnect")
async def disconnect_mcp_server(name: str) -> dict:
    """Disconnect from an MCP server."""
    return {"status": "disconnected", "name": name}


@router.get("/tools")
async def list_mcp_tools() -> List[dict]:
    """List all tools from connected MCP servers."""
    # In production, this aggregates tools from all connected servers
    return []
