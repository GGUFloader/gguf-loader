"""Agent routes - control agent execution and expose structured plan/phase state."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_model_backend, get_workspace
from ggufloader.core.agent.presets import PresetManager

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
    """Approve or deny a tool call.

    Forwards into the same ApprovalManager the WebSocket path uses, so a
    REST approval resolves the running agent's pending request instead of
    being a no-op echo.
    """
    from ggufloader.api.websocket.handler import get_approval_manager
    resolved = get_approval_manager().resolve(req.call_id, req.approved)
    return {"call_id": req.call_id, "approved": req.approved, "resolved": resolved}


@router.get("/presets")
async def list_presets() -> list:
    """List available agent presets with metadata."""
    pm = PresetManager()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "icon": p.icon,
            "max_steps": p.max_steps,
            "max_tokens": p.max_tokens,
            "temperature": p.temperature,
            "auto_commit": p.auto_commit,
            "auto_test": p.auto_test,
            "auto_verify": p.auto_verify,
            "allowed_tools": p.allowed_tools,
            "blocked_tools": p.blocked_tools,
        }
        for p in pm.list_all()
    ]


@router.post("/preset/{preset}")
async def set_preset(preset: str) -> dict:
    """Set the agent preset."""
    global _agent_preset
    _agent_preset = preset
    return {"preset": preset}


@router.get("/sessions")
async def list_agent_sessions() -> list:
    """List past agent conversation threads from SQLite checkpoints."""
    import hashlib
    import os
    import sqlite3

    checkpoint_dir = os.path.join(os.path.expanduser("~"), ".ggufloader", "agent_checkpoints")
    if not os.path.isdir(checkpoint_dir):
        return []

    sessions = []
    for fname in os.listdir(checkpoint_dir):
        if not fname.endswith(".db"):
            continue
        db_path = os.path.join(checkpoint_dir, fname)
        try:
            conn = sqlite3.connect(db_path)
            # Check for thread IDs in the checkpoints table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'"
            )
            if cursor.fetchone() is None:
                conn.close()
                continue
            cursor = conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints ORDER BY rowid DESC LIMIT 10"
            )
            thread_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            for tid in thread_ids:
                sessions.append({
                    "thread_id": tid,
                    "workspace_hash": fname.replace(".db", ""),
                    "status": "active" if _agent_running else "idle",
                    "preset": _agent_preset,
                })
        except Exception:
            continue
    return sessions


@router.get("/health")
async def agent_health() -> dict:
    """Get agent health status, cost summary, and audit stats."""
    from ggufloader.core.agent.health_monitor import HealthMonitor
    from ggufloader.core.agent.cost_estimator import CostEstimator
    from ggufloader.core.agent.rate_limiter import RateLimiter

    health = HealthMonitor()
    cost = CostEstimator()
    limiter = RateLimiter()

    return {
        "health": health.health_check(),
        "cost": cost.summary(),
        "rate_limiter": limiter.get_stats(),
        "agent_running": _agent_running,
        "preset": _agent_preset,
    }


@router.get("/replays")
async def list_replays() -> list:
    """List saved replay sessions."""
    import os
    from pathlib import Path

    workspace = get_workspace() or "."
    replay_dir = Path(workspace) / ".gguf-replays"
    if not replay_dir.is_dir():
        return []

    sessions = []
    for f in sorted(replay_dir.glob("*.json"), reverse=True)[:20]:
        try:
            import json
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "filename": f.name,
                "session_id": data.get("session_id", ""),
                "title": data.get("title", ""),
                "steps": len(data.get("steps", [])),
            })
        except Exception:
            continue
    return sessions


@router.get("/exports")
async def list_exports() -> list:
    """List exported sessions."""
    from pathlib import Path

    workspace = get_workspace() or "."
    export_dir = Path(workspace) / ".gguf-sessions"
    if not export_dir.is_dir():
        return []

    sessions = []
    for f in sorted(export_dir.glob("*.json"), reverse=True)[:20]:
        try:
            import json
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "filename": f.name,
                "title": data.get("title", ""),
                "exported_at": data.get("exported_at", ""),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            continue
    return sessions


# ---------------------------------------------------------------------------
# Profiling endpoints
# ---------------------------------------------------------------------------

@router.get("/profile/history")
async def profile_history(limit: int = 10) -> list:
    """Get profiling history for recent agent runs."""
    from ggufloader.core.agent.profiler import AgentProfiler
    profiler = AgentProfiler()
    return profiler.get_history(limit)


@router.get("/profile/steps")
async def profile_steps(limit: int = 1) -> list:
    """Get detailed step breakdown for recent runs."""
    from ggufloader.core.agent.profiler import AgentProfiler
    profiler = AgentProfiler()
    return profiler.get_step_breakdown(limit)


@router.get("/profile/bottlenecks")
async def profile_bottlenecks() -> dict:
    """Analyze bottlenecks across all profiled runs."""
    from ggufloader.core.agent.profiler import AgentProfiler
    profiler = AgentProfiler()
    return profiler.analyze_bottlenecks()


@router.get("/profile/throughput")
async def profile_throughput() -> list:
    """Get rolling token throughput data."""
    from ggufloader.core.agent.profiler import AgentProfiler
    profiler = AgentProfiler()
    return profiler.get_throughput_history()


# ---------------------------------------------------------------------------
# MCP endpoints
# ---------------------------------------------------------------------------

@router.get("/mcp/servers")
async def agent_mcp_servers() -> list:
    """List MCP servers known to the agent."""
    from ggufloader.core.agent.mcp_bridge import MCPBridge
    from pathlib import Path
    bridge = MCPBridge(Path(get_workspace() or "."))
    return bridge.get_status()


@router.get("/mcp/tools")
async def agent_mcp_tools() -> list:
    """List all tools discovered from connected MCP servers."""
    from ggufloader.core.agent.mcp_bridge import MCPBridge
    from pathlib import Path
    bridge = MCPBridge(Path(get_workspace() or "."))
    return bridge.get_all_tools()


# ---------------------------------------------------------------------------
# Model hot-swap endpoints
# ---------------------------------------------------------------------------

class HotSwapRequest(BaseModel):
    path: str
    n_ctx: int = 4096
    n_gpu_layers: int = -1
    fallback: bool = True
    fallback_chain: Optional[List[str]] = None


@router.get("/model/status")
async def agent_model_status() -> dict:
    """Get current model hot-swap status."""
    backend = get_model_backend()
    return {
        "loaded": backend is not None,
        "path": getattr(backend, "model_path", None) if backend else None,
    }


@router.post("/model/switch")
async def agent_model_switch(req: HotSwapRequest) -> dict:
    """Hot-swap to a new model without restarting the agent."""
    from ggufloader.core.agent.model_hotswap import ModelHotSwap

    def load_model(path, n_ctx=4096, n_gpu_layers=-1):
        from ggufloader.services.model_service import ModelService
        svc = ModelService()
        return svc.load(path, use_gpu=n_gpu_layers != 0, n_ctx=n_ctx)

    def unload_model():
        from ggufloader.services.model_service import ModelService
        svc = ModelService()
        svc.unload()

    swap = ModelHotSwap(load_fn=load_model, unload_fn=unload_model)
    if req.fallback_chain:
        swap.set_fallback_chain(req.fallback_chain)
    return swap.switch_to(req.path, n_ctx=req.n_ctx, n_gpu_layers=req.n_gpu_layers, fallback=req.fallback)


@router.post("/model/unload")
async def agent_model_unload() -> dict:
    """Unload the current model."""
    from ggufloader.services.model_service import ModelService
    svc = ModelService()
    svc.unload()
    return {"status": "unloaded"}


# ---------------------------------------------------------------------------
# Workflow Builder endpoints
# ---------------------------------------------------------------------------

@router.get("/workflows")
async def list_workflows() -> list:
    """List all saved workflows."""
    from ggufloader.core.agent.workflow_builder import WorkflowBuilder
    wb = WorkflowBuilder()
    return [w.to_dict() for w in wb.list_all()]


@router.get("/workflows/templates")
async def workflow_templates() -> list:
    """List available workflow templates."""
    from ggufloader.core.agent.workflow_builder import WorkflowBuilder
    wb = WorkflowBuilder()
    return wb.list_templates()


@router.post("/workflows")
async def create_workflow(req: dict) -> dict:
    """Create a new workflow."""
    from ggufloader.core.agent.workflow_builder import WorkflowBuilder, Workflow
    wb = WorkflowBuilder()
    import hashlib, time
    wf_id = hashlib.sha256(f"{req.get('name', '')}_{time.time()}".encode()).hexdigest()[:8]
    wf = Workflow(id=wf_id, name=req.get('name', 'Untitled'), description=req.get('description', ''), steps=[], tags=req.get('tags', []))
    wb.save(wf)
    return {"status": "created", "id": wf_id}


@router.post("/workflows/{workflow_id}/duplicate")
async def duplicate_workflow(workflow_id: str) -> dict:
    """Duplicate a workflow."""
    from ggufloader.core.agent.workflow_builder import WorkflowBuilder
    wb = WorkflowBuilder()
    new_wf = wb.duplicate(workflow_id)
    if not new_wf:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"status": "duplicated", "id": new_wf.id, "name": new_wf.name}


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str) -> dict:
    """Delete a workflow."""
    from ggufloader.core.agent.workflow_builder import WorkflowBuilder
    wb = WorkflowBuilder()
    deleted = wb.delete(workflow_id)
    return {"status": "deleted" if deleted else "not_found"}


@router.post("/workflows/{workflow_id}/validate")
async def validate_workflow(workflow_id: str) -> dict:
    """Validate a workflow DAG."""
    from ggufloader.core.agent.workflow_builder import WorkflowBuilder
    wb = WorkflowBuilder()
    wf = wb.get(workflow_id)
    if not wf:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Workflow not found")
    errors = wf.validate()
    return {"valid": len(errors) == 0, "errors": errors, "execution_order": wf.execution_order()}


@router.post("/workflows/{workflow_id}/dry-run")
async def dry_run_workflow(workflow_id: str) -> dict:
    """Dry-run a workflow."""
    from ggufloader.core.agent.workflow_builder import WorkflowBuilder
    wb = WorkflowBuilder()
    return wb.execute_dry_run(workflow_id)


@router.post("/workflows/{workflow_id}/from-template")
async def create_from_template(workflow_id: str, req: dict = {}) -> dict:
    """Create a workflow from a template."""
    from ggufloader.core.agent.workflow_builder import WorkflowBuilder
    wb = WorkflowBuilder()
    wf = wb.create_from_template(workflow_id, req.get('name', ''))
    if not wf:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "created", **wf.to_dict()}


# ---------------------------------------------------------------------------
# Collaboration endpoints
# ---------------------------------------------------------------------------

class CollabJoinRequest(BaseModel):
    session_id: str
    user_id: str = ""
    user_name: str = "Anonymous"


@router.post("/collab/join")
async def collab_join(req: CollabJoinRequest) -> dict:
    """Join a collaborative session."""
    from ggufloader.core.agent.collaboration import get_collab_manager
    mgr = get_collab_manager()
    user_id = req.user_id or mgr.generate_user_id()
    collab = mgr.join_session(req.session_id, user_id, req.user_name)
    return {"collaborator": collab.to_dict(), "session": mgr.get_session_info(req.session_id)}


@router.post("/collab/leave")
async def collab_leave(session_id: str, user_id: str) -> dict:
    """Leave a collaborative session."""
    from ggufloader.core.agent.collaboration import get_collab_manager
    mgr = get_collab_manager()
    mgr.leave_session(session_id, user_id)
    return {"status": "left"}


@router.get("/collab/session/{session_id}")
async def collab_session(session_id: str) -> dict:
    """Get collaborative session info."""
    from ggufloader.core.agent.collaboration import get_collab_manager
    mgr = get_collab_manager()
    return mgr.get_session_info(session_id)


@router.get("/collab/active")
async def collab_active() -> list:
    """Get all active collaborative sessions."""
    from ggufloader.core.agent.collaboration import get_collab_manager
    mgr = get_collab_manager()
    return mgr.get_active_sessions()

