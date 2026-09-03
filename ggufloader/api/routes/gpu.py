"""GPU routes - install and status check."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from ggufloader.api.deps import refresh_router_system
from ggufloader.core.system_probe import llama_cpp_available, llama_supports_gpu_offload

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status")
async def gpu_status() -> dict:
    """Check GPU support status."""
    if not llama_cpp_available():
        return {"gpu_available": False, "status": "not_installed"}
    has_gpu = llama_supports_gpu_offload()
    return {
        "gpu_available": has_gpu,
        "status": "installed" if has_gpu else "cpu_only",
    }


@router.post("/install")
async def install_gpu() -> dict:
    """Install GPU support (triggers background installation)."""
    # This would trigger the GPU install service
    # For now, return a placeholder
    # A re-detection lets the router's SystemProfile see the new GPU.
    refresh_router_system()
    return {"status": "installation_started", "message": "GPU installation initiated"}
