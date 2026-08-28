"""Agent routes - control agent execution."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_model_backend, get_workspace

router = APIRouter()
logger = logging.getLogger(__name__)

# Agent state
_agent_running = False
_agent_preset = "standard"


class AgentStartRequest(BaseModel):
    preset: str = "standard"
    workspace: Optional[str] = None
    max_steps: int = 10


class ApprovalRequest(BaseModel):
    call_id: str
    approved: bool


@router.get("/status")
async def agent_status() -> dict:
    """Get agent status."""
    return {
        "running": _agent_running,
        "preset": _agent_preset,
        "model_loaded": get_model_backend() is not None,
        "workspace": get_workspace(),
    }


@router.post("/start")
async def start_agent(req: AgentStartRequest) -> dict:
    """Start agent execution."""
    global _agent_running, _agent_preset
    if _agent_running:
        raise HTTPException(status_code=409, detail="Agent already running")

    if get_model_backend() is None:
        raise HTTPException(status_code=400, detail="No model loaded")

    _agent_running = True
    _agent_preset = req.preset
    return {"status": "started", "preset": req.preset}


@router.post("/stop")
async def stop_agent() -> dict:
    """Stop agent execution."""
    global _agent_running
    _agent_running = False
    return {"status": "stopped"}


@router.post("/approve")
async def approve_tool(req: ApprovalRequest) -> dict:
    """Approve or deny a tool call."""
    return {"call_id": req.call_id, "approved": req.approved}


@router.post("/preset/{preset}")
async def set_preset(preset: str) -> dict:
    """Set the agent preset."""
    global _agent_preset
    _agent_preset = preset
    return {"preset": preset}
