"""Session routes - CRUD, fork, and search."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.config import get_paths

router = APIRouter()
logger = logging.getLogger(__name__)


class SessionInfo(BaseModel):
    id: str
    title: Optional[str] = None
    created: str
    updated: str
    mode: str = "chat"
    message_count: int = 0


class SessionCreate(BaseModel):
    title: Optional[str] = None
    mode: str = "chat"


@router.get("")
async def list_sessions() -> List[SessionInfo]:
    """List all saved sessions."""
    try:
        from ggufloader.core.sessions.store import SessionStore
        store = SessionStore(get_paths()["chats"])
        sessions = store.list_sessions()
        return [
            SessionInfo(
                id=s["id"],
                title=s.get("title"),
                created=s.get("created", ""),
                updated=s.get("updated", ""),
                mode=s.get("mode", "chat"),
                message_count=len(s.get("messages", [])),
            )
            for s in sessions
        ]
    except Exception as e:
        logger.error("Failed to list sessions: %s", e)
        return []


@router.post("")
async def create_session(req: SessionCreate) -> dict:
    """Create a new session."""
    try:
        from ggufloader.core.sessions.store import SessionStore
        store = SessionStore(get_paths()["chats"])
        session = store.create(mode=req.mode)
        if req.title:
            session["title"] = req.title
        store.save(session)
        return {"id": session["id"], "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get session messages."""
    try:
        from ggufloader.core.sessions.store import SessionStore
        store = SessionStore(get_paths()["chats"])
        session = store.load(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RenameRequest(BaseModel):
    title: str


@router.put("/{session_id}")
async def rename_session(session_id: str, req: RenameRequest) -> dict:
    """Rename a session."""
    try:
        from ggufloader.core.sessions.store import SessionStore
        store = SessionStore(get_paths()["chats"])
        session = store.load(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session["title"] = req.title
        store.save(session)
        return {"status": "renamed", "title": req.title}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete a session."""
    try:
        from ggufloader.core.sessions.store import SessionStore
        store = SessionStore(get_paths()["chats"])
        store.delete(session_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/fork")
async def fork_session(session_id: str) -> dict:
    """Fork a session from a specific point."""
    try:
        from ggufloader.core.sessions.store import SessionStore
        store = SessionStore(get_paths()["chats"])
        session = store.load(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        # Create new session with same messages
        new_session = store.create()
        new_session["title"] = f"Fork of {session.get('title', session_id)}"
        new_session["messages"] = session.get("messages", []).copy()
        store.save(new_session)
        new_id = new_session["id"]
        return {"id": new_id, "status": "forked"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/{query}")
async def search_sessions(query: str) -> List[dict]:
    """Search across all sessions."""
    try:
        from ggufloader.core.sessions.store import SessionStore
        store = SessionStore(get_paths()["chats"])
        results = store.search(query) if hasattr(store, "search") else []
        return results
    except Exception as e:
        logger.error("Session search failed: %s", e)
        return []
