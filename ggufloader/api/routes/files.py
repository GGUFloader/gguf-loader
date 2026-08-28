"""File routes - workspace file operations."""

from __future__ import annotations

import logging
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_workspace

router = APIRouter()
logger = logging.getLogger(__name__)

# Blocked commands for safety
BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=", "format",
    "shutdown", "reboot", "halt", "sudo rm",
    "git push --force", "git reset --hard",
}


class FileNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    children: Optional[List["FileNode"]] = None


class FileContent(BaseModel):
    path: str
    content: str
    size: int


class WriteRequest(BaseModel):
    path: str
    content: str


@router.get("/tree")
async def file_tree(path: Optional[str] = None) -> List[FileNode]:
    """Get workspace file tree."""
    root = path or get_workspace() or "."
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")

    def build_tree(dir_path: str, max_depth: int = 3, depth: int = 0) -> List[FileNode]:
        if depth >= max_depth:
            return []
        nodes = []
        try:
            for entry in sorted(os.listdir(dir_path)):
                if entry.startswith(".") or entry in ("node_modules", "__pycache__", ".git"):
                    continue
                full_path = os.path.join(dir_path, entry)
                is_dir = os.path.isdir(full_path)
                node = FileNode(
                    name=entry,
                    path=full_path,
                    is_dir=is_dir,
                    children=build_tree(full_path, max_depth, depth + 1) if is_dir else None,
                )
                nodes.append(node)
        except PermissionError:
            pass
        return nodes

    return build_tree(root)


@router.get("/content")
async def read_file(path: str) -> FileContent:
    """Read file content."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    if os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Cannot read a directory")

    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        return FileContent(
            path=path,
            content=content[:50_000],  # Limit to 50KB
            size=os.path.getsize(path),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/content")
async def write_file(req: WriteRequest) -> dict:
    """Write file content."""
    try:
        Path(req.path).write_text(req.content, encoding="utf-8")
        return {"status": "written", "path": req.path, "size": len(req.content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_files(q: str) -> List[dict]:
    """Search workspace files by name."""
    workspace = get_workspace() or "."
    results = []
    for root, dirs, files in os.walk(workspace):
        # Skip hidden and ignored dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
        for f in files:
            if q.lower() in f.lower():
                full_path = os.path.join(root, f)
                results.append({"name": f, "path": full_path})
                if len(results) >= 50:
                    return results
    return results


class CommandRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout: int = 30


@router.post("/run")
async def run_command(req: CommandRequest) -> dict:
    """Execute a shell command in the workspace."""
    # Safety check
    cmd_lower = req.command.lower().strip()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            raise HTTPException(status_code=400, detail=f"Blocked command: {blocked}")

    workspace = req.cwd or get_workspace() or "."

    try:
        result = subprocess.run(
            req.command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=workspace,
            timeout=req.timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        return {
            "stdout": result.stdout[:10_000],
            "stderr": result.stderr[:10_000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Command timed out", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}


# --- Git routes ---

@router.get("/git/status")
async def git_status() -> dict:
    """Get git status for the workspace."""
    workspace = get_workspace() or "."
    try:
        # Check if git repo
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=workspace, capture_output=True, check=True,
        )

        # Get branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=workspace, capture_output=True, text=True,
        )
        branch = branch_result.stdout.strip() or "detached"

        # Get status
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace, capture_output=True, text=True,
        )

        files = []
        for line in status_result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            status_code = line[:2].strip()
            filepath = line[3:]
            status_map = {
                "M": "modified", "A": "added", "D": "deleted",
                "R": "renamed", "??": "untracked",
            }
            files.append({
                "path": filepath,
                "status": status_map.get(status_code, "modified"),
            })

        # Ahead/behind
        ab_result = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
            cwd=workspace, capture_output=True, text=True,
        )
        ahead, behind = 0, 0
        if ab_result.returncode == 0:
            parts = ab_result.stdout.strip().split("\t")
            ahead, behind = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0

        return {
            "branch": branch,
            "files": files,
            "ahead": ahead,
            "behind": behind,
            "clean": len(files) == 0,
        }
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=400, detail="Not a git repository")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/git/diff")
async def git_diff(path: Optional[str] = None) -> dict:
    """Get diff for a file."""
    workspace = get_workspace() or "."
    try:
        args = ["git", "diff"]
        if path:
            args.append(path)
        result = subprocess.run(
            args, cwd=workspace, capture_output=True, text=True, timeout=10,
        )
        return {"diff": result.stdout[:20_000]}
    except Exception as e:
        return {"diff": f"Error: {e}"}


class CommitRequest(BaseModel):
    message: str
    files: Optional[List[str]] = None


@router.post("/git/commit")
async def git_commit(req: CommitRequest) -> dict:
    """Stage all changes and commit."""
    workspace = get_workspace() or "."
    try:
        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=workspace, capture_output=True, check=True,
        )
        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", req.message],
            cwd=workspace, capture_output=True, text=True, timeout=10,
        )
        return {
            "status": "committed" if result.returncode == 0 else "failed",
            "output": result.stdout + result.stderr,
        }
    except Exception as e:
        return {"status": "error", "output": str(e)}
