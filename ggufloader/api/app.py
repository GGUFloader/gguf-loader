"""FastAPI application for GGUFLoader.

Wraps existing services (ModelService, ChatService, SessionStore, AgentEngine)
with a REST/WebSocket API for the React frontend.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ggufloader.api.routes import agent, chat, files, files_render, gpu, model, session, mcp, tools, workflows, plugins, templates, branching, workspaces, search, benchmark, sandbox
from ggufloader.api.websocket.handler import websocket_endpoint
from ggufloader._version import __version__
from ggufloader.config import (
    APP_NAME,
    PINNED_ARCH,
    PINNED_MODEL_LABEL,
    PINNED_QUANT,
    PINNED_SIZE,
    PINNED_TAGLINE,
)

logger = logging.getLogger(__name__)

# The uvicorn.Server the launcher (ggufloader.main) is running. Registered
# there so /api/shutdown can ask it to stop when the Electron window closes;
# None when the app is run directly (uvicorn CLI, TestClient, dev).
_active_server = None

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup/shutdown lifecycle."""
    logger.info("GGUFLoader API starting...")
    # Set the workspace from the active workspace on startup
    try:
        from ggufloader.core.agent.workspace_manager import WorkspaceManager
        from ggufloader.api.deps import set_workspace
        mgr = WorkspaceManager()
        active = mgr.active
        if active and active.path:
            set_workspace(active.path)
            logger.info("Active workspace: %s (%s)", active.name, active.path)
    except Exception as e:
        logger.warning("Failed to set active workspace: %s", e)
    # Background scan + load of the pinned Gemma 4 12B Q4_K_M GGUF from the
    # models folder (start_auto_load spawns a daemon thread and returns
    # immediately; it is a no-op under pytest / GGUFLOADER_SKIP_AUTOLOAD).
    from ggufloader.api.auto_load import start_auto_load
    try:
        status = start_auto_load()
        logger.info("Auto-load at startup: %s", status.get("status"))
    except Exception as e:  # noqa: BLE001 - never block boot on scan failures
        logger.warning("Auto-load startup check failed: %s", e)
    yield
    logger.info("GGUFLoader API shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="GGUFLoader API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS for React dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:8000",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    app.include_router(model.router, prefix="/api/model", tags=["model"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(session.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
    app.include_router(files.router, prefix="/api/files", tags=["files"])
    app.include_router(files_render.router, prefix="/api/files", tags=["files-render"])
    app.include_router(gpu.router, prefix="/api/gpu", tags=["gpu"])
    app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])
    app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
    app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
    app.include_router(plugins.router, prefix="/api/plugins", tags=["plugins"])
    app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
    app.include_router(branching.router, prefix="/api/branching", tags=["branching"])
    app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
    app.include_router(search.router, prefix="/api/search", tags=["search"])
    app.include_router(benchmark.router, prefix="/api/benchmark", tags=["benchmark"])
    app.include_router(sandbox.router, prefix="/api/sandbox", tags=["sandbox"])

    # WebSocket endpoint
    app.websocket("/ws")(websocket_endpoint)

    # Health check
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": __version__}

    # Graceful close: the Electron shell calls this when the user closes
    # the window. Unload the model first (frees the multi-GB context), then
    # stop the server so the packaged launcher process can exit.
    @app.post("/api/shutdown")
    async def shutdown() -> dict:
        """Unload the model and stop the backend process."""
        from ggufloader.api.deps import get_model_backend, set_model_backend

        backend = get_model_backend()
        if backend is not None:
            try:
                unload = getattr(backend, "unload", None)
                if callable(unload):
                    unload()
            except Exception as e:  # noqa: BLE001 - shutdown must still proceed
                logger.warning("Error unloading model at shutdown: %s", e)
        set_model_backend(None)

        server = _active_server
        if server is not None:
            server.should_exit = True
            # Failsafe: if the process is somehow still alive shortly after
            # the graceful stop (lingering thread), force-exit so the app
            # never stays resident with the model in memory.
            threading.Timer(3.0, os._exit, args=(0,)).start()
        return {"status": "shutting_down"}

    # App-level identity: drives the version banner and the
    # first-launch model-compatibility dialog in the React UI.
    @app.get("/api/app/info")
    async def app_info():
        return {
            "name": APP_NAME,
            "version": __version__,
            "label": PINNED_MODEL_LABEL,
            "tagline": PINNED_TAGLINE,
            "pinned": {
                "arch": PINNED_ARCH,
                "quant": PINNED_QUANT,
                "size": PINNED_SIZE,
            },
        }

    # Serve built React frontend in production
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        # Mount static assets
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="static")

        # SPA fallback: serve index.html for all non-API routes
        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str = ""):
            # Don't intercept API or WebSocket routes
            if full_path.startswith("api/") or full_path == "ws":
                return None
            # Serve the file if it exists, otherwise serve index.html (SPA routing)
            file_path = FRONTEND_DIST / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:
        logger.info("No built frontend found. Serving API only. Use Vite dev server for UI.")

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ggufloader.api.app:create_app", host="127.0.0.1", port=8000, reload=True)
