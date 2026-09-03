"""Model routes - load, unload, info, estimate, and rich router."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_model_backend, set_model_backend, get_router
from ggufloader.core.llm.model_backend import ModelBackend
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
            "suggested_role": router.suggest_role(profile).value,
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


@router.get("/router/route")
async def router_route(path: str, role: str = "chat") -> dict:
    """Get sampling params tuned for a specific role (chat/agent/code/embed/reasoning)."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    router = get_router()
    try:
        profile = router.inspect(path)
        try:
            model_role = ModelRole(role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown role: {role}")
        config = router.route(profile, model_role)
        return {
            "role": config.role.value,
            "temperature": config.temperature,
            "top_k": config.top_k,
            "top_p": config.top_p,
            "min_p": config.min_p,
            "repeat_penalty": config.repeat_penalty,
            "max_tokens": config.max_tokens,
            "notes": config.notes,
            "can_serve": router.can_serve_role(profile, model_role),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Router route failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/router/quick")
async def router_quick(path: str) -> dict:
    """Quick lightweight profile for file picker / catalog (no deep analysis)."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    router = get_router()
    try:
        return router.quick_profile(path)
    except Exception as e:
        logger.error("Router quick profile failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/router/system")
async def router_system() -> dict:
    """Get system capabilities (RAM, VRAM, GPU, CPU)."""
    router = get_router()
    s = router.system
    return {
        "ram_gb": s.ram_gb,
        "vram_gb": s.vram_gb,
        "gpu_name": s.gpu_name,
        "gpu_backend": s.gpu_backend,
        "cpu_cores": s.cpu_cores,
        "has_gpu_support": s.has_gpu_support,
    }


@router.post("/router/auto-load")
async def router_auto_load(req: dict) -> dict:
    """Load a model with full router optimization: inspect → plan → load.

    Accepts: {"path": str, "role"?: str, "n_ctx"?: int, "use_gpu"?: bool, "n_gpu_layers"?: int}
    """
    path = req.get("path", "")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    role_str = req.get("role", "chat")
    try:
        model_role = ModelRole(role_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role_str}")

    router = get_router()
    try:
        backend, profile, strategy, config = router.load(
            path, model_role,
            n_ctx=req.get("n_ctx"),
            use_gpu=req.get("use_gpu"),
            n_gpu_layers=req.get("n_gpu_layers"),
        )
        set_model_backend(backend)
        return {
            "status": "loaded",
            "path": path,
            "role": model_role.value,
            "profile": {
                "family": profile.family,
                "family_label": profile.family_label,
                "size_tier": profile.size_tier.value,
                "architecture": profile.architecture,
                "total_layers": profile.total_layers,
                "quantization": profile.quantization,
                "total_memory_gb": profile.total_memory_gb,
            },
            "strategy": {
                "n_ctx": strategy.n_ctx,
                "n_gpu_layers": strategy.n_gpu_layers,
                "use_gpu": strategy.use_gpu,
                "batch_size": strategy.batch_size,
                "reasoning": strategy.reasoning,
                "fallback_chain": strategy.fallback_chain,
            },
            "config": {
                "temperature": config.temperature,
                "top_k": config.top_k,
                "top_p": config.top_p,
                "repeat_penalty": config.repeat_penalty,
                "max_tokens": config.max_tokens,
                "notes": config.notes,
            },
        }
    except Exception as e:
        logger.error("Router auto-load failed: %s", e)
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


# ---------------------------------------------------------------------------
# Model comparison: side-by-side deep profiles
# ---------------------------------------------------------------------------

@router.get("/compare")
async def model_compare(paths: str) -> dict:
    """Compare two or more GGUF models side-by-side.

    paths: comma-separated list of model file paths
    Returns deep profiles for each model plus a diff summary.
    """
    path_list = [p.strip() for p in paths.split(",") if p.strip()]
    if len(path_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 comma-separated paths")

    profiles = []
    router = get_router()

    for path in path_list[:5]:  # max 5 models
        if not os.path.exists(path):
            profiles.append({"path": path, "error": "File not found"})
            continue
        try:
            profile = router.inspect(path)
            strategy = router.plan(profile)
            profiles.append({
                "path": profile.path,
                "filename": profile.filename,
                "file_size_gb": profile.file_size_gb,
                "architecture": profile.architecture,
                "family": profile.family,
                "family_label": profile.family_label,
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
                "strategy": {
                    "n_ctx": strategy.n_ctx,
                    "n_gpu_layers": strategy.n_gpu_layers,
                    "use_gpu": strategy.use_gpu,
                    "batch_size": strategy.batch_size,
                    "fits_vram": strategy.fits_vram,
                    "fits_ram": strategy.fits_ram,
                    "reasoning": strategy.reasoning,
                },
            })
        except Exception as e:
            profiles.append({"path": path, "error": str(e)})

    # Build comparison summary
    valid = [p for p in profiles if "error" not in p]
    comparison = {}
    if len(valid) >= 2:
        comparison = {
            "size_diff_gb": round(valid[0].get("file_size_gb", 0) - valid[1].get("file_size_gb", 0), 2),
            "memory_diff_gb": round(valid[0].get("total_memory_gb", 0) - valid[1].get("total_memory_gb", 0), 2),
            "same_family": valid[0].get("family") == valid[1].get("family"),
            "same_architecture": valid[0].get("architecture") == valid[1].get("architecture"),
            "smaller_model": valid[0].get("filename") if valid[0].get("file_size_gb", 0) < valid[1].get("file_size_gb", 0) else valid[1].get("filename"),
            "higher_context": valid[0].get("filename") if valid[0].get("trained_context", 0) > valid[1].get("trained_context", 0) else valid[1].get("filename"),
        }

    return {
        "models": profiles,
        "comparison": comparison,
        "system": {
            "ram_gb": router.system.ram_gb,
            "vram_gb": router.system.vram_gb,
        },
    }
