"""Sandbox routes - WASM plugin sandbox management."""

from __future__ import annotations

import logging
import shutil
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class PluginLoadRequest(BaseModel):
    wasm_path: str
    manifest_path: Optional[str] = None
    max_memory_mb: Optional[int] = None
    max_cpu_time_s: Optional[int] = None


class PluginCallRequest(BaseModel):
    function: str = "process"
    input_data: dict = {}
    timeout_ms: Optional[int] = None


@router.get("/status")
async def sandbox_status() -> dict:
    """Get sandbox status."""
    from ggufloader.core.agent.wasm_sandbox import get_sandbox
    return get_sandbox().status()


@router.get("/plugins")
async def list_plugins_dir() -> list:
    """List available WASM plugin files."""
    from ggufloader.core.agent.wasm_sandbox import get_sandbox
    return get_sandbox().list_plugins_dir()


@router.get("/instances")
async def list_instances() -> list:
    """List loaded plugin instances."""
    from ggufloader.core.agent.wasm_sandbox import get_sandbox
    instances = get_sandbox().list_instances()
    return [i.to_dict() for i in instances]


@router.post("/load")
async def load_plugin(req: PluginLoadRequest) -> dict:
    """Load a WASM plugin."""
    from pathlib import Path
    from ggufloader.core.agent.wasm_sandbox import get_sandbox, ResourceLimits

    limits = None
    if req.max_memory_mb or req.max_cpu_time_s:
        limits = ResourceLimits(
            max_memory_bytes=(req.max_memory_mb or 64) * 1024 * 1024,
            max_cpu_time_ms=(req.max_cpu_time_s or 30) * 1000,
        )

    try:
        instance = get_sandbox().load_plugin(
            wasm_path=Path(req.wasm_path),
            manifest_path=Path(req.manifest_path) if req.manifest_path else None,
            limits=limits,
        )
        return {"status": "loaded", "instance": instance.to_dict()}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


class UploadRequest(BaseModel):
    filename: str
    content_b64: str  # base64-encoded WASM content


@router.post("/upload")
async def upload_plugin(req: UploadRequest) -> dict:
    """Upload and load a WASM plugin (base64-encoded)."""
    import base64
    from pathlib import Path
    from ggufloader.core.agent.wasm_sandbox import get_sandbox

    sandbox = get_sandbox()
    dest = sandbox._plugins_dir / req.filename
    dest.write_bytes(base64.b64decode(req.content_b64))

    instance = sandbox.load_plugin(wasm_path=dest)
    return {"status": "uploaded", "instance": instance.to_dict()}


@router.delete("/instances/{instance_id}")
async def unload_plugin(instance_id: str) -> dict:
    """Unload a WASM plugin instance."""
    from ggufloader.core.agent.wasm_sandbox import get_sandbox

    unloaded = get_sandbox().unload_plugin(instance_id)
    if not unloaded:
        raise HTTPException(status_code=404, detail="Plugin instance not found")
    return {"status": "unloaded", "instance_id": instance_id}


@router.post("/instances/{instance_id}/call")
async def call_plugin(instance_id: str, req: PluginCallRequest) -> dict:
    """Call a function on a WASM plugin."""
    from ggufloader.core.agent.wasm_sandbox import get_sandbox

    result = get_sandbox().call_plugin(
        instance_id, req.function, req.input_data, req.timeout_ms,
    )
    return result.to_dict()


@router.get("/instances/{instance_id}/metrics")
async def plugin_metrics(instance_id: str) -> dict:
    """Get resource usage metrics for a plugin."""
    from ggufloader.core.agent.wasm_sandbox import get_sandbox

    metrics = get_sandbox().get_metrics(instance_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Plugin instance not found")
    return metrics


@router.delete("/plugins/{filename}")
async def delete_plugin_file(filename: str) -> dict:
    """Delete a WASM plugin file from the plugins directory."""
    from ggufloader.core.agent.wasm_sandbox import get_sandbox

    path = get_sandbox()._plugins_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Plugin file not found")
    path.unlink()
    # Also remove manifest if exists
    manifest = path.with_suffix(".json")
    if manifest.exists():
        manifest.unlink()
    return {"status": "deleted", "filename": filename}
