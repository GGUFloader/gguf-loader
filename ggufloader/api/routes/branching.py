"""Branching routes - session branching, timeline, and diff viewer."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_workspace

router = APIRouter()
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Branching
# -------------------------------------------------------------------

class BranchRequest(BaseModel):
    session_id: str
    branch_id: str
    message_index: int
    name: str = ""


class MergeRequest(BaseModel):
    session_id: str
    source_branch: str
    target_branch: str
    strategy: str = "append"


class DiffRequest(BaseModel):
    session_id: str
    branch_a: str
    branch_b: str


@router.get("/{session_id}/branches")
async def list_branches(session_id: str) -> List[dict]:
    """List all branches in a session."""
    from pathlib import Path
    from ggufloader.core.agent.branching import SessionBranching

    workspace = Path(get_workspace()) if get_workspace() else None
    sb = SessionBranching(workspace)
    sb.load(session_id)
    return sb.list_branches()


@router.get("/{session_id}/timeline")
async def get_timeline(session_id: str) -> List[dict]:
    """Get the visual timeline of a session's branches."""
    from pathlib import Path
    from ggufloader.core.agent.branching import SessionBranching

    workspace = Path(get_workspace()) if get_workspace() else None
    sb = SessionBranching(workspace)
    sb.load(session_id)
    return sb.get_timeline()


@router.post("/{session_id}/fork")
async def fork_branch(session_id: str, req: BranchRequest) -> dict:
    """Fork a branch from a specific message index."""
    from pathlib import Path
    from ggufloader.core.agent.branching import SessionBranching

    workspace = Path(get_workspace()) if get_workspace() else None
    sb = SessionBranching(workspace)
    sb.load(session_id)
    branch = sb.fork(req.branch_id, req.message_index, req.name)
    if not branch:
        raise HTTPException(status_code=404, detail="Source branch not found or invalid index")
    sb.save(session_id)
    return {"status": "forked", "branch_id": branch.id, "name": branch.name}


@router.post("/{session_id}/merge")
async def merge_branches(session_id: str, req: MergeRequest) -> dict:
    """Merge a source branch into a target branch."""
    from pathlib import Path
    from ggufloader.core.agent.branching import SessionBranching

    workspace = Path(get_workspace()) if get_workspace() else None
    sb = SessionBranching(workspace)
    sb.load(session_id)
    success = sb.merge(req.source_branch, req.target_branch, req.strategy)
    if not success:
        raise HTTPException(status_code=400, detail="Merge failed: branch not found")
    sb.save(session_id)
    return {"status": "merged", "strategy": req.strategy}


@router.post("/{session_id}/diff")
async def diff_branches(session_id: str, req: DiffRequest) -> dict:
    """Show differences between two branches."""
    from pathlib import Path
    from ggufloader.core.agent.branching import SessionBranching

    workspace = Path(get_workspace()) if get_workspace() else None
    sb = SessionBranching(workspace)
    sb.load(session_id)
    return sb.diff_branches(req.branch_a, req.branch_b)


@router.get("/{session_id}/messages/{branch_id}")
async def get_branch_messages(session_id: str, branch_id: str) -> List[dict]:
    """Get messages in a specific branch."""
    from pathlib import Path
    from ggufloader.core.agent.branching import SessionBranching

    workspace = Path(get_workspace()) if get_workspace() else None
    sb = SessionBranching(workspace)
    sb.load(session_id)
    return sb.get_branch_messages(branch_id)


# -------------------------------------------------------------------
# Diff Viewer
# -------------------------------------------------------------------

class DiffComputeRequest(BaseModel):
    old_text: str
    new_text: str
    filename: str = ""


class DiffFromResultsRequest(BaseModel):
    tool_results: List[dict]


@router.post("/diff/compute")
async def compute_diff(req: DiffComputeRequest) -> dict:
    """Compute a unified diff between two texts."""
    from ggufloader.core.agent.diff_viewer import compute_diff
    return compute_diff(req.old_text, req.new_text, req.filename)


@router.post("/diff/side-by-side")
async def side_by_side_diff(req: DiffComputeRequest) -> dict:
    """Compute a side-by-side diff."""
    from ggufloader.core.agent.diff_viewer import compute_side_by_side
    return compute_side_by_side(req.old_text, req.new_text, req.filename)


@router.post("/diff/from-results")
async def diff_from_results(req: DiffFromResultsRequest) -> List[dict]:
    """Extract diffs from agent tool call results."""
    from ggufloader.core.agent.diff_viewer import extract_diffs_from_tool_results
    return extract_diffs_from_tool_results(req.tool_results)
