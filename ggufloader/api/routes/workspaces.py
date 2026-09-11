"""Workspace routes - multi-workspace management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class WorkspaceCreate(BaseModel):
    name: str
    path: str = ""


class WorkspaceRename(BaseModel):
    name: str


@router.get("")
async def list_workspaces() -> list:
    """List all workspaces."""
    from ggufloader.core.agent.workspace_manager import WorkspaceManager
    mgr = WorkspaceManager()
    workspaces = mgr.list_all()
    return [
        {**ws.to_dict(), "is_active": ws.id == mgr.active_id, "stats": mgr.get_stats(ws.id)}
        for ws in workspaces
    ]


@router.get("/active")
async def active_workspace() -> dict:
    """Get the active workspace."""
    from ggufloader.core.agent.workspace_manager import WorkspaceManager
    mgr = WorkspaceManager()
    ws = mgr.active
    if not ws:
        return {"active": None}
    return {**ws.to_dict(), "stats": mgr.get_stats()}


@router.post("")
async def create_workspace(req: WorkspaceCreate) -> dict:
    """Create a new workspace."""
    from ggufloader.core.agent.workspace_manager import WorkspaceManager
    mgr = WorkspaceManager()
    ws = mgr.create(req.name, req.path)
    return {"status": "created", **ws.to_dict()}


@router.post("/{workspace_id}/switch")
async def switch_workspace(workspace_id: str) -> dict:
    """Switch to a different workspace."""
    from ggufloader.core.agent.workspace_manager import WorkspaceManager
    from ggufloader.api.deps import set_workspace
    mgr = WorkspaceManager()
    success = mgr.switch_to(workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws = mgr.active
    if ws and ws.path:
        set_workspace(ws.path)
    return {"status": "switched", **ws.to_dict()}


@router.put("/{workspace_id}")
async def rename_workspace(workspace_id: str, req: WorkspaceRename) -> dict:
    """Rename a workspace."""
    from ggufloader.core.agent.workspace_manager import WorkspaceManager
    mgr = WorkspaceManager()
    success = mgr.rename(workspace_id, req.name)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "renamed"}


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str) -> dict:
    """Delete a workspace."""
    from ggufloader.core.agent.workspace_manager import WorkspaceManager
    mgr = WorkspaceManager()
    success = mgr.delete(workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "deleted"}


@router.get("/{workspace_id}/settings")
async def get_workspace_settings(workspace_id: str) -> dict:
    """Get workspace-specific settings."""
    from ggufloader.core.agent.workspace_manager import WorkspaceManager
    mgr = WorkspaceManager()
    return mgr.get_settings(workspace_id)


@router.put("/{workspace_id}/settings")
async def save_workspace_settings(workspace_id: str, settings: dict) -> dict:
    """Save workspace-specific settings."""
    from ggufloader.core.agent.workspace_manager import WorkspaceManager
    mgr = WorkspaceManager()
    mgr.save_settings(settings, workspace_id)
    return {"status": "saved"}
