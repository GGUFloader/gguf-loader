"""Workflow routes - manage agent workflows."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    steps: List[dict] = []


@router.get("")
async def list_workflows() -> List[dict]:
    """List all available workflows."""
    from ggufloader.core.agent.workflow_engine import WorkflowEngine
    engine = WorkflowEngine()
    workflows = engine.list_workflows()
    return [{"id": w.id, "name": w.name, "description": w.description, "status": "idle"} for w in workflows]


@router.post("")
async def create_workflow(req: WorkflowCreate) -> dict:
    """Create a new workflow."""
    from ggufloader.core.agent.workflow_engine import WorkflowEngine
    engine = WorkflowEngine()
    wf = engine.create_workflow(req.name, req.description)
    return {"id": wf.id, "name": wf.name, "status": "created"}


@router.get("/templates")
async def list_workflow_templates() -> List[dict]:
    """List available workflow templates."""
    return [
        {"id": "research", "name": "Research", "description": "Search and summarize information"},
        {"id": "code_review", "name": "Code Review", "description": "Review code for issues"},
        {"id": "refactor", "name": "Refactor", "description": "Analyze and refactor code"},
        {"id": "document", "name": "Documentation", "description": "Generate documentation"},
        {"id": "test", "name": "Testing", "description": "Write and run tests"},
    ]


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str) -> dict:
    """Start executing a workflow."""
    return {"status": "started", "workflow_id": workflow_id}
