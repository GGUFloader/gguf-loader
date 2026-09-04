"""Model routes - load, unload, info, estimate, and rich router."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.auto_load import (
    auto_load_status,
    pinned_download_status,
    start_pinned_download,
)
from ggufloader.api.deps import get_model_backend, set_model_backend, get_router
from ggufloader.core.llm.model_profiles import resolve_chat_config, read_gguf_general_metadata
from ggufloader.core.router import ModelRole

router = APIRouter()
logger = logging.getLogger(__name__)


class LoadRequest(BaseModel):
    path: str
    use_gpu: bool | None = None      # None = auto-detect via router
    n_ctx: int | None = None         # None = router picks (auto contract)
    n_gpu_layers: int | None = None  # None = router picks
    role: str = "chat"


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
    # Startup auto-load state (see api/auto_load.py): idle|scanning|loading|
    # loaded|not_found|error|disabled plus a human message and the folder
    # the app scans for the pinned GGUF.
    auto_load: Optional[str] = None
    auto_load_message: Optional[str] = None
    models_dir: Optional[str] = None
    # Pinned-target compatibility of the currently loaded model. False when
    # a model somehow got loaded despite the gate (e.g. older session state);
    # None when nothing is loaded.
    compatible: Optional[bool] = None
    compatible_error: Optional[str] = None


PINNED_ARCH = "gemma4"


def pinned_target_error(profile) -> Optional[str]:
    """Return a human message if profile is NOT the pinned target, else None.

    Single source of truth shared by the load gate below and the startup
    auto-loader (api/auto_load.py). Multi-model auto-detection was removed;
    any other GGUF is rejected loudly instead of running with mismatched
    sampling or prompts.
    """
    arch = (profile.architecture or "").lower()
    quant_blob = ((profile.quantization or "") + " " + profile.filename).upper()
    param_blob = ((profile.param_count_estimate or "") + " " + profile.filename).upper()
    if arch != PINNED_ARCH:
        return (
            f"Unsupported model: architecture '{profile.architecture}'. "
            "This build is pinned to Gemma 4 12B Instruct (Q4_K_M) only."
        )
    if "Q4_K_M" not in quant_blob:
        return (
            f"Unsupported quantization: '{profile.quantization}'. "
            "This build is pinned to Gemma 4 12B Instruct Q4_K_M only."
        )
    if "12B" not in param_blob:
        return (
            f"Unsupported size: '{profile.param_count_estimate}'. "
            "This build is pinned to Gemma 4 12B Instruct (Q4_K_M) only."
        )
    return None


def _require_pinned_target(profile) -> None:
    """HTTP load gate: raise 400 unless profile is the pinned target."""
    err = pinned_target_error(profile)
    if err:
        raise HTTPException(status_code=400, detail=err)


@router.get("/info")
async def model_info() -> ModelInfo:
    """Get info about the currently loaded model + startup auto-load state."""
    auto = auto_load_status()

    backend = get_model_backend()
    if backend is None:
        return ModelInfo(
            loaded=False,
            auto_load=auto.get("status"),
            auto_load_message=auto.get("message"),
            models_dir=auto.get("models_dir"),
        )

    path = getattr(backend, "model_path", None)
    filename = os.path.basename(path) if path else None

    # Resolve full chat config from model profiles
    chat_config = None
    family = None
    family_label = None
    detected_via = None
    architecture = getattr(backend, "architecture", None)
    quantization = getattr(backend, "quantization", None)
    parameters = getattr(backend, "parameters", None)
    compatible = None
    compatible_error = None
    if path:
        # Pinned-target verdict comes from the cached router inspect (single
        # source shared with the load gate).
        try:
            profile = get_router().inspect(path)
            architecture = profile.architecture
            quantization = profile.quantization
            parameters = profile.param_count_estimate
            err = pinned_target_error(profile)
            compatible = err is None
            compatible_error = err
        except Exception as e:
            logger.warning("Failed to inspect loaded model: %s", e)
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
        architecture=architecture,
        quantization=quantization,
        parameters=parameters,
        context_length=getattr(backend, "n_ctx", None),
        gpu=getattr(backend, "use_gpu", False),
        chat_config=chat_config,
        auto_load=auto.get("status"),
        auto_load_message=auto.get("message"),
        models_dir=auto.get("models_dir"),
        compatible=compatible,
        compatible_error=compatible_error,
    )


@router.post("/load")
async def load_model(req: LoadRequest) -> dict:
    """Load a GGUF model. Router decides; null fields mean "auto".

    Any of n_ctx / use_gpu / n_gpu_layers being null delegates that
    decision to the router's plan; explicit values override it and are
    still verified against real memory before the load ladder runs.
    """
    if not os.path.exists(req.path):
        raise HTTPException(status_code=404, detail=f"File not found: {req.path}")

    try:
        try:
            role = ModelRole(req.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown role: {req.role}")

        router = get_router()
        # Single-model gate (metadata-only inspect, cached).
        _require_pinned_target(router.inspect(req.path))
        backend, profile, strategy, _config = router.load(
            req.path,
            role,
            n_ctx=req.n_ctx,
            use_gpu=req.use_gpu,
            n_gpu_layers=req.n_gpu_layers,
        )
        set_model_backend(backend)
        return {
            "status": "loaded",
            "path": req.path,
            "filename": profile.filename,
            "strategy": {
                "n_ctx": strategy.n_ctx,
                "n_gpu_layers": strategy.n_gpu_layers,
                "use_gpu": strategy.use_gpu,
                "batch_size": strategy.batch_size,
                "fits_vram": strategy.fits_vram,
                "fits_ram": strategy.fits_ram,
                "fallback_chain": strategy.fallback_chain,
                "attempts": strategy.attempts,
                "reasoning": strategy.reasoning,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Model load failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unload")
async def unload_model() -> dict:
    """Unload the current model."""
    set_model_backend(None)
    return {"status": "unloaded"}


@router.post("/download")
async def download_pinned_model() -> dict:
    """Start (or report state of) the pinned Gemma 4 12B Q4_K_M download.

    Downloads into the default models folder in the background; the file
    is auto-loaded once complete. Idempotent — safe to call repeatedly.
    """
    return start_pinned_download()


@router.get("/download/status")
async def download_pinned_status() -> dict:
    """Poll download progress: idle|downloading|done|error|disabled + 0..1 progress."""
    return pinned_download_status()


@router.get("/estimate")
async def estimate_memory(path: str) -> dict:
    """Estimate RAM/VRAM needed for a model via the router's GQA-aware math."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    router = get_router()
    try:
        profile = router.inspect(path)
        strategy = router.plan(profile)
        total_gb = profile.model_memory_gb + profile.kv_memory_gb
        estimated_ram = int(total_gb * (1024 ** 3))
        # VRAM need at the planned ctx: model + KV when fully offloaded;
        # for partial plans report the GPU-resident share.
        if strategy.use_gpu and strategy.n_gpu_layers == -1:
            estimated_vram = estimated_ram
        elif strategy.use_gpu and profile.total_layers:
            frac = strategy.n_gpu_layers / profile.total_layers
            estimated_vram = int(
                (profile.model_memory_gb + profile.kv_memory_gb) * frac * (1024 ** 3))
        else:
            estimated_vram = 0
        return {
            "file_size": int(profile.file_size_gb * (1024 ** 3)),
            "estimated_ram_bytes": estimated_ram,
            "estimated_vram_bytes": estimated_vram,
            "file_size_human": _human_size(int(profile.file_size_gb * (1024 ** 3))),
            "estimated_ram_human": _human_size(estimated_ram),
            "estimated_vram_human": _human_size(estimated_vram) if estimated_vram > 0 else "N/A",
            "strategy": {
                "n_ctx": strategy.n_ctx,
                "n_gpu_layers": strategy.n_gpu_layers,
                "use_gpu": strategy.use_gpu,
                "reasoning": strategy.reasoning,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Router estimate failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Rich Router endpoints
# ------------------------------------------------------------------


@router.get("/router/inspect")
async def router_inspect(path: str) -> dict:
    """Deep-inspect a GGUF model: architecture, capabilities, size tier, memory."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    router = get_router()
    try:
        profile = router.inspect(path)
        return {
            "path": profile.path,
            "filename": profile.filename,
            "file_size_gb": profile.file_size_gb,
            "architecture": profile.architecture,
            "family": profile.family,
            "family_label": profile.family_label,
            "detected_via": profile.detected_via,
            "size_tier": profile.size_tier.value,
            "param_estimate": profile.param_count_estimate,
            "total_layers": profile.total_layers,
            "quantization": profile.quantization,
            "quant_tier": profile.quant_tier.value,
            "trained_context": profile.trained_context,
            "max_context": profile.max_context,
            "supports_system_prompt": profile.supports_system_prompt,
            "supports_vision": profile.supports_vision,
            "is_embedding_model": profile.is_embedding_model,
            "is_thinking_model": profile.is_thinking_model,
            "model_memory_gb": profile.model_memory_gb,
            "kv_memory_gb": profile.kv_memory_gb,
            "total_memory_gb": profile.total_memory_gb,
            "family_params": profile.family_params,
        }
    except Exception as e:
        logger.error("Router inspect failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/router/plan")
async def router_plan(
    path: str,
    n_ctx: Optional[int] = None,
    use_gpu: Optional[bool] = None,
    n_gpu_layers: Optional[int] = None,
) -> dict:
    """Plan the optimal loading strategy for a model on this system.

    Optional overrides are honored AND fits are recomputed against the
    real memory budget, so the UI can show "wanted 32k, fits? no".
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    router = get_router()
    try:
        profile = router.inspect(path)
        if any(v is not None for v in (n_ctx, use_gpu, n_gpu_layers)):
            strategy = router.plan_with_overrides(
                profile, n_ctx=n_ctx, use_gpu=use_gpu, n_gpu_layers=n_gpu_layers)
        else:
            strategy = router.plan(profile)
        return {
            "n_ctx": strategy.n_ctx,
            "n_gpu_layers": strategy.n_gpu_layers,
            "use_gpu": strategy.use_gpu,
            "batch_size": strategy.batch_size,
            "reasoning": strategy.reasoning,
            "fits_vram": strategy.fits_vram,
            "fits_ram": strategy.fits_ram,
            "fallback_chain": strategy.fallback_chain,
            "system": {
                "ram_gb": router.system.ram_gb,
                "vram_gb": router.system.vram_gb,
                "gpu_name": router.system.gpu_name,
                "gpu_backend": router.system.gpu_backend,
                "cpu_cores": router.system.cpu_cores,
                "has_gpu_support": router.system.has_gpu_support,
            },
        }
    except Exception as e:
        logger.error("Router plan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# ---------------------------------------------------------------------------
# Model catalog: scan directories for GGUF files with deep profiles
# ---------------------------------------------------------------------------

@router.get("/catalog")
async def model_catalog(
    directory: Optional[str] = None,
    recursive: bool = True,
) -> dict:
    """Scan a directory for GGUF files and return deep profiles.

    If no directory is given, scans the user's default models directory.
    Returns a list of models with family, architecture, quantization,
    size, context length, and router-ready profile data.
    """
    from ggufloader.config import get_paths

    if directory:
        scan_dir = Path(directory)
    else:
        scan_dir = Path(get_paths()["models"]) if "models" in get_paths() else Path.home() / ".ggufloader" / "models"

    if not scan_dir.is_dir():
        return {"directory": str(scan_dir), "models": [], "error": "Directory not found"}

    glob_pattern = "**/*.gguf" if recursive else "*.gguf"
    gguf_files = sorted(scan_dir.glob(glob_pattern))

    models = []
    for f in gguf_files:
        try:
            size_bytes = f.stat().st_size
            size_gb = round(size_bytes / (1024**3), 2)

            # Quick metadata read
            meta = {}
            try:
                meta = read_gguf_general_metadata(str(f))
            except Exception:
                pass

            # Router inspection (lightweight)
            profile_data = {}
            try:
                profile = get_router().quick_profile(str(f))
                profile_data = {
                    "family": profile.get("family", ""),
                    "architecture": profile.get("architecture", ""),
                    "size_tier": profile.get("size_tier", ""),
                    "context_length": profile.get("context_length", 0),
                    "quantization": profile.get("quantization", ""),
                }
            except Exception:
                pass

            models.append({
                "path": str(f),
                "filename": f.name,
                "directory": str(f.parent),
                "size_gb": size_gb,
                "size_human": _human_size(size_bytes),
                **profile_data,
                "metadata": {k: str(v)[:200] for k, v in meta.items()} if meta else {},
            })
        except Exception:
            continue

    return {
        "directory": str(scan_dir),
        "count": len(models),
        "models": models,
    }


