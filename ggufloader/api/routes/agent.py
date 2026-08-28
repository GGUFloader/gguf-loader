"""Agent routes - control agent execution and expose structured plan/phase state."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_model_backend, get_workspace

router = APIRouter()
logger = logging.getLogger(__name__)

# Agent state
_agent_running = False
_agent_preset = "standard"

# Current plan/phase state (updated by WebSocket handler during agent runs)
_current_plan: List[Dict[str, Any]] = []
_current_phase: str = "idle"
_phase_log: List[str] = []
_current_goal: str = ""
_plan_step: Optional[Dict[str, Any]] = None


class AgentStartRequest(BaseModel):
    preset: str = "standard"
    workspace: Optional[str] = None
    max_steps: int = 10


class ApprovalRequest(BaseModel):
    call_id: str
    approved: bool


def update_plan_state(
    phase: str = "idle",
    plan: Optional[List[Dict[str, Any]]] = None,
    phase_log: Optional[List[str]] = None,
    goal: str = "",
    plan_step: Optional[Dict[str, Any]] = None,
) -> None:
    """Update the current plan/phase state. Called by WebSocket handler."""
    global _current_plan, _current_phase, _phase_log, _current_goal, _plan_step
    if phase:
        _current_phase = phase
    if plan is not None:
        _current_plan = plan
    if phase_log is not None:
        _phase_log = phase_log
    if goal:
        _current_goal = goal
    if plan_step is not None:
        _plan_step = plan_step


@router.get("/status")
async def agent_status() -> dict:
    """Get agent status."""
    return {
        "running": _agent_running,
        "preset": _agent_preset,
        "model_loaded": get_model_backend() is not None,
        "workspace": get_workspace(),
    }


@router.get("/plan")
async def get_plan() -> dict:
    """Get the current structured plan, phase, and phase log."""
    return {
        "phase": _current_phase,
        "goal": _current_goal,
        "plan": _current_plan,
        "plan_step": _plan_step,
        "phase_log": _phase_log,
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
