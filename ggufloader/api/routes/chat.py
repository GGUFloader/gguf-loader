"""Chat routes - send messages, streaming, and workspace dashboard."""

from __future__ import annotations

import json
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ggufloader.api.deps import get_model_backend, get_workspace

router = APIRouter()
logger = logging.getLogger(__name__)


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 4096


class ChatResponse(BaseModel):
    response: str
    tokens_used: int = 0
    finish_reason: str = "stop"


@router.post("/send")
async def send_message(req: ChatRequest) -> ChatResponse:
    """Send a chat message (non-streaming fallback).

    For streaming, use the WebSocket endpoint at /ws.
    """
    backend = get_model_backend()
    if backend is None:
        raise HTTPException(status_code=400, detail="No model loaded")

    try:
        # Build messages list
        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.append({"role": "user", "content": req.message})

        # Generate (non-streaming)
        response = backend.chat(
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )

        return ChatResponse(
            response=response,
            tokens_used=len(response.split()),
            finish_reason="stop",
        )
    except Exception as e:
        logger.error("Chat generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_message(req: ChatRequest):
    """Stream a chat response via Server-Sent Events (SSE).

    Returns an event stream with:
      - event: token  data: {"token": "..."}
      - event: done   data: {"content": "...", "tokens_used": N}
      - event: error  data: {"message": "..."}
    """
    backend = get_model_backend()
    if backend is None:
        raise HTTPException(status_code=400, detail="No model loaded")

    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.message})

    def event_stream():
        try:
            if hasattr(backend, 'chat_stream'):
                full = []
                for token in backend.chat_stream(
                    messages=messages,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                ):
                    full.append(token)
                    yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
                content = "".join(full)
            else:
                content = backend.chat(
                    messages=messages,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                )
            yield f"event: done\ndata: {json.dumps({'content': content, 'tokens_used': len(content.split())})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
async def chat_health() -> dict:
    """Check if the model is ready for chat."""
    backend = get_model_backend()
    return {
        "model_loaded": backend is not None,
        "model_path": getattr(backend, "model_path", None) if backend else None,
    }


# ---------------------------------------------------------------------------
# Workspace Dashboard endpoint
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def workspace_dashboard() -> dict:
    """Workspace dashboard: plugins, memory, active sessions, model info."""
    import os
    from pathlib import Path

    workspace = get_workspace() or "."
    ws_path = Path(workspace)

    # --- Plugins ---
    plugins = []
    try:
        from ggufloader.core.agent.plugin_manager import PluginManager
        pm = PluginManager(ws_path)
        plugins = [{"name": p, "status": "loaded"} for p in pm.get_loaded()]
    except Exception:
        pass

    # --- Memory ---
    memory = {"entries": [], "count": 0}
    try:
        from ggufloader.core.agent.memory_persistence import MemoryPersistence
        mem = MemoryPersistence()
        entries = mem.search("") if hasattr(mem, 'search') else []
        if not entries and hasattr(mem, 'get_all'):
            entries = mem.get_all()
        memory = {"entries": entries[:50], "count": len(entries)}
    except Exception:
        pass

    # --- Active sessions ---
    sessions = []
    try:
        from ggufloader.core.sessions.store import SessionStore
        from ggufloader.config import get_paths
        store = SessionStore(get_paths()["chats"])
        raw = store.list_sessions()
        sessions = [
            {
                "id": s["id"],
                "title": s.get("title", ""),
                "messages": len(s.get("messages", [])),
                "updated": s.get("updated", ""),
            }
            for s in raw[:20]
        ]
    except Exception:
        pass

    # --- Model info ---
    backend = get_model_backend()
    model = None
    if backend:
        model = {
            "loaded": True,
            "path": getattr(backend, "model_path", None),
            "filename": os.path.basename(getattr(backend, "model_path", "")) if getattr(backend, "model_path", None) else None,
        }

    # --- System resources ---
    import shutil
    ram_gb = round(shutil.disk_usage("/").total / (1024**3), 1) if hasattr(shutil, 'disk_usage') else 0
    try:
        import psutil
        mem_info = psutil.virtual_memory()
        ram_gb = round(mem_info.total / (1024**3), 1)
    except ImportError:
        pass

    return {
        "workspace": workspace,
        "plugins": plugins,
        "memory": memory,
        "sessions": sessions,
        "model": model,
        "ram_gb": ram_gb,
    }
