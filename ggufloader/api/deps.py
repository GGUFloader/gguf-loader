"""Dependency injection for GGUFLoader services.

Services are lazily initialized on first access. The React frontend
connects to these via REST/WebSocket without needing Qt.
"""

from __future__ import annotations

import logging
from typing import Optional

from ggufloader.core.llm.model_backend import ModelBackend
from ggufloader.core.router import ModelRouter

logger = logging.getLogger(__name__)

# Global state (lazy initialized)
_model_backend: Optional[ModelBackend] = None
_workspace: Optional[str] = None
_router: Optional[ModelRouter] = None


def get_model_backend() -> Optional[ModelBackend]:
    """Get the currently loaded model backend."""
    return _model_backend


def set_model_backend(backend: Optional[ModelBackend]) -> None:
    """Set the model backend after loading."""
    global _model_backend
    _model_backend = backend
    if backend:
        logger.info("Model backend set: %s", backend.model_path)
    else:
        logger.info("Model backend cleared")


def get_workspace() -> Optional[str]:
    """Get the current workspace directory."""
    return _workspace


def set_workspace(path: Optional[str]) -> None:
    """Set the workspace directory."""
    global _workspace
    _workspace = path
    logger.info("Workspace set to: %s", path)


def get_router() -> ModelRouter:
    """Get or create the global ModelRouter instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def refresh_router_system() -> None:
    """Re-detect RAM/VRAM/GPU support after a hardware-level change.

    Call after a GPU install/upgrade so future plans reflect reality
    instead of a stale SystemProfile captured at first use.
    """
    global _router
    if _router is not None:
        _router.system.refresh()
        logger.info("Router system profile refreshed")
    # If no router exists yet, the next get_router() detects fresh anyway.


def is_model_loaded() -> bool:
    """Check if a model is currently loaded."""
    return _model_backend is not None
