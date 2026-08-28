"""Chat routes - send messages and trigger streaming."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_model_backend

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
        response = ""
        for token in backend.generate_stream(
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        ):
            response += token

        return ChatResponse(
            response=response,
            tokens_used=len(response.split()),
            finish_reason="stop",
        )
    except Exception as e:
        logger.error("Chat generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def chat_health() -> dict:
    """Check if the model is ready for chat."""
    backend = get_model_backend()
    return {
        "model_loaded": backend is not None,
        "model_path": getattr(backend, "model_path", None) if backend else None,
    }
