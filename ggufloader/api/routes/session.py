"""Session routes - CRUD, fork, and search."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

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
                message_count=s.get("message_count", 0),
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
        return {
            "id": session["id"],
            "title": session.get("title"),
            "created": session.get("created", ""),
            "updated": session.get("updated", ""),
            "mode": session.get("mode", "chat"),
            "message_count": len(session.get("messages", [])),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MessageAppend(BaseModel):
    role: str
    content: str
    steps: Optional[List[Any]] = None


@router.post("/{session_id}/messages")
async def append_message(session_id: str, req: MessageAppend) -> dict:
    """Append a message to a session."""
    try:
        from ggufloader.core.sessions.store import SessionStore
        store = SessionStore(get_paths()["chats"])
        session = store.load(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        store.append_message(
            session,
            req.role,
            req.content,
            extra={"steps": req.steps} if req.steps is not None else None,
        )
        store.save(session)
        return {"status": "appended", "title": session.get("title")}
    except HTTPException:
        raise
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
        return {
            "id": new_session["id"],
            "title": new_session.get("title"),
            "created": new_session.get("created", ""),
            "updated": new_session.get("updated", ""),
            "mode": new_session.get("mode", "chat"),
            "message_count": len(new_session.get("messages", [])),
            "status": "forked",
        }
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


@router.get("/{session_id}/export")
async def export_session(session_id: str, format: str = "json") -> dict:
    """Export a session as JSON, Markdown, or HTML."""
    try:
        from ggufloader.core.sessions.store import SessionStore
        import html as html_mod
        store = SessionStore(get_paths()["chats"])
        session = store.load(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        title = session.get("title", "Untitled")
        messages = session.get("messages", [])

        if format == "markdown":
            lines = [f"# {title}", ""]
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                lines.append(f"## {role.title()}")
                lines.append("")
                lines.append(content)
                lines.append("")
            return {"format": "markdown", "content": "\n".join(lines)}

        if format == "html":
            msg_html = []
            for msg in messages:
                role = msg.get("role", "unknown")
                content = html_mod.escape(msg.get("content", ""))
                bg = "#1a202c" if role == "assistant" else "#e8a33d"
                color = "#e7ebf2" if role == "assistant" else "#0b0e14"
                align = "left" if role == "assistant" else "right"
                msg_html.append(
                    f'<div style="display:flex;justify-content:{align};margin:12px 0">'
                    f'<div style="max-width:70%;padding:12px 16px;border-radius:16px;'
                    f'background:{bg};color:{color};font-family:system-ui;'
                    f'white-space:pre-wrap;line-height:1.5">{content}</div>'
                    f'</div>'
                )
            full_html = (
                '<!DOCTYPE html>\n<html><head>'
                f'<title>{html_mod.escape(title)}</title>'
                '<style>body{background:#0b0e14;margin:0;padding:20px 40px;}'
                'h1{color:#e7ebf2;font-family:system-ui;}</style>'
                '</head><body>'
                f'<h1>{html_mod.escape(title)}</h1>'
                + "\n".join(msg_html)
                + '</body></html>'
            )
            return {"format": "html", "content": full_html}

        # Default: JSON
        return {"format": "json", "content": session}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
