"""Model routes - load, unload, info, estimate."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_model_backend, set_model_backend
from ggufloader.core.llm.model_backend import ModelBackend
from ggufloader.core.llm.model_profiles import resolve_chat_config, read_gguf_general_metadata

router = APIRouter()
logger = logging.getLogger(__name__)


class LoadRequest(BaseModel):
    path: str
    use_gpu: bool = False
    n_ctx: int = 32768
    n_gpu_layers: int = -1


class ModelInfo(BaseModel):
    loaded: bool
    path: Optional[str] = None
    filename: Optional[str] = None
    family: Optional[str] = None
    family_label: Optional[str] = None
    detected_via: Optional[str] = None
    architecture: Optional[str] = None
    quantization: Optional[str] = None
    parameters: Optional[str] = None
    context_length: Optional[int] = None
    gpu: bool = False
    chat_config: Optional[dict] = None


@router.get("/info")
async def model_info() -> ModelInfo:
    """Get info about the currently loaded model."""
    backend = get_model_backend()
    if backend is None:
        return ModelInfo(loaded=False)

    path = getattr(backend, "model_path", None)
    filename = os.path.basename(path) if path else None

    # Resolve full chat config from model profiles
    chat_config = None
    family = None
    family_label = None
    detected_via = None
    if path:
        try:
            chat_config = resolve_chat_config(path)
            family = chat_config.get("family")
            family_label = chat_config.get("label")
            detected_via = chat_config.get("detected_via")
        except Exception as e:
            logger.warning("Failed to resolve chat config: %s", e)

    return ModelInfo(
        loaded=True,
        path=path,
        filename=filename,
        family=family,
        family_label=family_label,
        detected_via=detected_via,
        architecture=getattr(backend, "architecture", None),
        quantization=getattr(backend, "quantization", None),
        parameters=getattr(backend, "parameters", None),
        context_length=getattr(backend, "n_ctx", None),
        gpu=getattr(backend, "use_gpu", False),
        chat_config=chat_config,
    )


@router.post("/load")
async def load_model(req: LoadRequest) -> dict:
    """Load a GGUF model file."""
    if not os.path.exists(req.path):
        raise HTTPException(status_code=404, detail=f"File not found: {req.path}")

    try:
        backend = ModelBackend(
            req.path,
            use_gpu=req.use_gpu,
            n_ctx=req.n_ctx,
            n_gpu_layers=req.n_gpu_layers,
        )
        backend.load()
        set_model_backend(backend)
        return {"status": "loaded", "path": req.path}
    except Exception as e:
        logger.error("Model load failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unload")
async def unload_model() -> dict:
    """Unload the current model."""
    set_model_backend(None)
    return {"status": "unloaded"}


@router.get("/profile")
async def model_profile(path: str) -> dict:
    """Get auto-detected chat config for a model file (without loading it)."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    try:
        return resolve_chat_config(path)
    except Exception as e:
        logger.warning("Profile detection failed: %s", e)
        return {"family": "unknown", "label": "Unknown", "params": {}, "supports_system_prompt": True}


@router.get("/estimate")
async def estimate_memory(path: str) -> dict:
    """Estimate VRAM/RAM needed for a model file."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    file_size = os.path.getsize(path)
    # Rough estimate: model size * 1.2 for overhead
    estimated_ram = int(file_size * 1.2)
    estimated_vram = int(file_size * 0.8) if file_size > 1_000_000_000 else 0

    return {
        "file_size": file_size,
        "estimated_ram_bytes": estimated_ram,
        "estimated_vram_bytes": estimated_vram,
        "file_size_human": _human_size(file_size),
        "estimated_ram_human": _human_size(estimated_ram),
        "estimated_vram_human": _human_size(estimated_vram) if estimated_vram > 0 else "N/A",
    }


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
