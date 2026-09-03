"""
ModelRouter — rich, universal router for GGUF models.

Extends the existing model-profile detection with:
  • Multi-dimensional model profiling (architecture, role, size tier, quant)
  • Adaptive load strategy (context, GPU layers, batch) given system resources
  • Role-based routing (chat vs agent vs embed vs code — each gets tuned params)
  • Model switching: hot-swap backends for different tasks
  • Capability detection (vision, function calling, reasoning, thinking)

This module is pure Python, Qt-free, and unit-testable.

Design:
  ModelRouter.inspect(path)  → ModelProfile  (metadata + inferred capabilities)
  ModelRouter.plan(profile)  → LoadStrategy   (ctx, gpu_layers, batch)
  ModelRouter.route(profile, role) → dict      (sampling params for that role)
  ModelRouter.load(path, role)     → backend   (inspects + plans + loads)

The existing resolve_chat_config() is preserved as-is for backward
compatibility; ModelRouter wraps it and adds the richer analysis.
"""

from __future__ import annotations

import json
import logging
import math
import os
import platform
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ggufloader.core.defaults import (
    CTX_OPTIONS,
    CUDA_RESERVE_GB,
    RAM_HEADROOM,
    VRAM_HEADROOM,
)

from ggufloader.core.system_probe import (  # noqa: E402
    llama_supports_gpu_offload,
    llama_supports_metal,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ModelRole(str, Enum):
    """What the model is being used for."""
    CHAT = "chat"
    AGENT = "agent"
    CODE = "code"
    EMBED = "embed"
    REASONING = "reasoning"
    MULTIMODAL = "multimodal"


class SizeTier(str, Enum):
    """Rough parameter-count tier, derived from file size + layer metadata."""
    TINY = "tiny"           # ≤ 1B params  (≤ 1 GB)
    SMALL = "small"         # 1–3B         (1–3 GB)
    MEDIUM = "medium"       # 3–8B         (3–6 GB)
    LARGE = "large"         # 8–14B        (6–10 GB)
    XLARGE = "xlarge"       # 14–30B       (10–20 GB)
    XXLARGE = "xxlarge"     # 30–70B       (20–45 GB)
    MEGA = "mega"           # 70B+         (45 GB+)


class QuantTier(str, Enum):
    """Quantization quality tier."""
    LOW = "low"             # Q2, IQ2
    MEDIUM = "medium"       # Q3, IQ3
    GOOD = "good"           # Q4, IQ4
    HIGH = "high"           # Q5, IQ5
    VERY_HIGH = "very_high" # Q6, Q8
    FULL = "full"           # F16, F32


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SystemProfile:
    """What the host machine offers."""
    ram_gb: float = 0.0
    vram_gb: float = 0.0
    gpu_name: str = ""
    gpu_backend: str = ""           # "cuda", "metal", "vulkan", ""
    cpu_cores: int = 0
    has_gpu_support: bool = False   # llama-cpp-python compiled with GPU?

    @classmethod
    def detect(cls) -> "SystemProfile":
        """Auto-detect system capabilities."""
        ram = _get_ram_gb()
        vram, gpu_name = _get_vram_info()
        cpu = os.cpu_count() or 1
        gpu_support = _check_gpu_support()
        gpu_backend = _detect_gpu_backend()
        return cls(
            ram_gb=round(ram, 1),
            vram_gb=round(vram, 1),
            gpu_name=gpu_name,
            gpu_backend=gpu_backend,
            cpu_cores=cpu,
            has_gpu_support=gpu_support,
        )

    def refresh(self) -> "SystemProfile":
        """Re-run detection in place (e.g. right after a GPU install)."""
        fresh = SystemProfile.detect()
        for name, value in vars(fresh).items():
            setattr(self, name, value)
        return self


@dataclass
class ModelProfile:
    """Multi-dimensional profile of a GGUF model file."""
    # Identity
    path: str = ""
    filename: str = ""
    file_size_gb: float = 0.0

    # Architecture
    architecture: str = ""          # "llama", "qwen3", "lfm2", etc.
    family: str = ""                # detected family ID
    family_label: str = ""          # human-readable family name
    detected_via: str = ""          # how we detected it

    # Size
    size_tier: SizeTier = SizeTier.MEDIUM
    param_count_estimate: str = ""  # "7B", "13B", etc. (from filename)
    total_layers: int = 0
    kv_heads: Optional[int] = None   # GQA: attention.head_count_kv
    head_dim: Optional[int] = None   # per-head dim (defaults to 128)
    quantization: str = ""          # "Q4_K_M", "Q8_0", etc.
    quant_tier: QuantTier = QuantTier.GOOD

    # Context
    trained_context: int = 0        # what the model was trained for
    max_context: int = 0            # GGUF metadata max context

    # Capabilities
    supports_system_prompt: bool = True
    supports_vision: bool = False
    supports_function_calling: bool = False
    is_embedding_model: bool = False
    is_thinking_model: bool = False  # chain-of-thought / reasoning models
    chat_template: str = ""

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Memory estimates
    model_memory_gb: float = 0.0
    kv_memory_gb: float = 0.0
    total_memory_gb: float = 0.0

    # From existing profile system
    family_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadStrategy:
    """Optimal loading parameters for a model on a given system."""
    n_ctx: int = 8192
    n_gpu_layers: int = -1         # -1 = auto (all layers)
    use_gpu: bool = False
    batch_size: int = 512
    n_threads: Optional[int] = None
    flash_attn: bool = True
    use_mmap: bool = True
    bytes_per_layer: float = 0.0   # model GB / total_layers (GB per layer)
    rope_freq_base: Optional[float] = None
    reasoning: str = ""            # human explanation of choices

    # Memory fit
    fits_vram: bool = False
    fits_ram: bool = False
    fallback_chain: List[str] = field(default_factory=list)  # what was tried
    attempts: List[str] = field(default_factory=list)        # ladder steps executed


@dataclass
class RoleConfig:
    """Sampling parameters for a specific use case."""
    role: ModelRole
    temperature: float = 0.7
    top_k: int = 40
    top_p: float = 0.9
    min_p: float = 0.0
    repeat_penalty: float = 1.05
    max_tokens: int = 4096
    system_prompt: Optional[str] = None
    task_prompts: Dict[str, str] = field(default_factory=dict)
    stop_tokens: List[str] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# The Router
# ---------------------------------------------------------------------------

class ModelRouter:
    """Universal GGUF model router.

    Usage:
        router = ModelRouter()
        profile = router.inspect("/path/to/model.gguf")
        strategy = router.plan(profile)
        config = router.route(profile, ModelRole.CHAT)
    """

    def __init__(self, system: Optional[SystemProfile] = None) -> None:
        self._system = system or SystemProfile.detect()
        # path+size+mtime → cached profile (stale file = re-inspect)
        self._profile_cache: Dict[Any, ModelProfile] = {}

    @property
    def system(self) -> SystemProfile:
        return self._system

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def inspect(self, path: str) -> ModelProfile:
        """Deep-inspect a GGUF file and return a multi-dimensional profile.

        Results are cached per path — the GGUF metadata only gets parsed once.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        # Cache is invalidated when the file changes on disk (ns precision
        # so two writes in the same second are still seen as distinct).
        st = p.stat()
        cache_key = (str(p.resolve()), st.st_size, st.st_mtime_ns)
        if cache_key in self._profile_cache:
            return self._profile_cache[cache_key]

        file_size_gb = st.st_size / (1024 ** 3)

        # Read GGUF metadata
        meta = _read_gguf_metadata(p)

        # Architecture & family
        arch = (meta.get("architecture") or "").lower()
        name = meta.get("name", "")
        basename = meta.get("basename", "")

        # Use existing family detection
        from ggufloader.core.llm.model_profiles import detect_family, GENERIC_PROFILE
        family_profile, detected_via = detect_family(meta, path)

        # Size tier from file size heuristic
        size_tier = _size_tier_from_gb(file_size_gb)
        param_estimate = _param_estimate_from_filename(p.name)
        if not param_estimate:
            param_estimate = _param_estimate_from_size(file_size_gb)

        # Layers
        total_layers = _extract_layers(meta, arch)

        # Quantization
        quant, quant_tier = _detect_quantization(p.name, meta)

        # Context
        trained_ctx = _extract_uint(meta, arch, "context_length")
        max_ctx = _extract_uint(meta, arch, "context_length")

        # Capabilities
        is_embed = _is_embedding_model(arch, name, basename)
        is_vision = _is_vision_model(arch, name, basename, meta)
        is_thinking = _is_thinking_model(arch, name, p.name)
        supports_sys = family_profile.get("supports_system_prompt", True)

        # Override with actual template detection
        chat_template = meta.get("chat_template", "")
        if chat_template:
            from ggufloader.core.llm.model_profiles import _template_supports_system
            supports_sys = _template_supports_system(chat_template)

        # Memory estimates (GQA-aware: KV heads + head dim from metadata)
        kv_heads = _extract_uint(meta, arch, "attention.head_count_kv") or None
        head_count = _extract_uint(meta, arch, "attention.head_count")
        embed_dim = _extract_uint(meta, arch, "embedding_length")
        head_dim = (embed_dim // head_count) if (head_count and embed_dim) else None
        model_gb, kv_gb, _bpl = _estimate_memory_detailed(
            file_size_gb, total_layers, max_ctx or 32768,
            kv_heads=kv_heads, head_dim=head_dim,
        )

        profile = ModelProfile(
            path=str(p),
            filename=p.name,
            file_size_gb=round(file_size_gb, 2),
            architecture=arch,
            family=family_profile.get("family", "generic"),
            family_label=family_profile.get("label", "Generic"),
            detected_via=detected_via,
            size_tier=size_tier,
            param_count_estimate=param_estimate,
            total_layers=total_layers,
            kv_heads=kv_heads,
            head_dim=head_dim,
            quantization=quant,
            quant_tier=quant_tier,
            trained_context=trained_ctx,
            max_context=max_ctx,
            supports_system_prompt=supports_sys,
            supports_vision=is_vision,
            is_embedding_model=is_embed,
            is_thinking_model=is_thinking,
            chat_template=chat_template,
            metadata=meta,
            model_memory_gb=round(model_gb, 2),
            kv_memory_gb=round(kv_gb, 2),
            total_memory_gb=round(model_gb + kv_gb, 2),
            family_params={
                k: v for k, v in family_profile.items()
                if k in ("temperature", "top_k", "top_p", "repeat_penalty",
                         "min_p", "max_tokens", "system_prompt", "task_prompts")
            },
        )

        logger.info(
            "Router inspect: %s | arch=%s family=%s tier=%s quant=%s "
            "layers=%d ctx=%d mem=%.1fGB",
            p.name, arch, profile.family, size_tier.value,
            quant, total_layers, max_ctx or 0, profile.total_memory_gb,
        )
        self._profile_cache[cache_key] = profile
        return profile

    # ------------------------------------------------------------------
    # Load strategy (adaptive to system)
    # ------------------------------------------------------------------

    def plan(self, profile: ModelProfile) -> LoadStrategy:
        """Determine the optimal loading strategy for this model on this system.

        Fit-aware: n_ctx is chosen so model + GQA KV cache fit inside
        RAM headroom (and, on GPU systems, preferably inside a reserve-
        aware VRAM budget). Partial offload leaves CUDA_RESERVE_GB free and
        charges each offloaded layer its share of the KV cache, not just
        its weight bytes.
        """
        sys = self._system
        reasoning_parts = []

        # --- Context size first: drives both RAM and VRAM KV cost ---
        n_ctx = self._optimal_context(profile, sys)
        if profile.trained_context > 0 and n_ctx != min(profile.trained_context, 32768):
            reasoning_parts.append(f"Context set to {n_ctx} (capped to fit this system)")

        ok_ram, ok_vram, kv_gb = self._ctx_fits(profile, sys, n_ctx)
        bpl = profile.model_memory_gb / profile.total_layers if profile.total_layers > 0 else 0.0

        use_gpu = False
        n_gpu_layers = 0
        if profile.is_embedding_model:
            reasoning_parts.append("Embedding model — CPU preferred for quick load/unload")
        elif not (sys.has_gpu_support and sys.vram_gb > 0):
            reasoning_parts.append("No GPU support — CPU mode")
        elif ok_vram:
            # Whole model + whole KV cache fits with the CUDA reserve intact.
            use_gpu = True
            n_gpu_layers = -1  # all layers
            reasoning_parts.append(
                f"Model+KV ({profile.model_memory_gb + kv_gb:.1f} GB) fits in VRAM "
                f"with 1 GB reserve — full GPU offload"
            )
        elif sys.vram_gb * VRAM_HEADROOM > CUDA_RESERVE_GB and bpl > 0 and ok_ram:
            # Reserve-aware partial offload: leave CUDA_RESERVE_GB free and
            # charge each GPU layer its proportional share of the KV cache
            # (llama.cpp places KV on the same device as its layer).
            avail = sys.vram_gb * VRAM_HEADROOM - CUDA_RESERVE_GB
            total_units = profile.model_memory_gb + kv_gb  # scales linearly w/ layers
            n_gpu_layers = int(avail * profile.total_layers / total_units)
            n_gpu_layers = max(1, min(profile.total_layers - 1, n_gpu_layers))
            if n_gpu_layers >= 1:
                use_gpu = True
                reasoning_parts.append(
                    f"Partial GPU offload: {n_gpu_layers} of {profile.total_layers} layers "
                    f"(reserve-aware: KV cache charged per offloaded layer)"
                )
            else:
                reasoning_parts.append("Model fits RAM but not VRAM — CPU mode")
        elif ok_ram:
            reasoning_parts.append(
                f"Model ({profile.model_memory_gb:.1f} GB) exceeds reserve-aware VRAM — CPU mode"
            )
        else:
            reasoning_parts.append(
                f"Model+KV does not fit RAM headroom at ctx {n_ctx} — smallest context"
            )

        batch = self._optimal_batch(profile, sys, n_ctx)

        strategy = LoadStrategy(
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            use_gpu=use_gpu,
            batch_size=batch,
            bytes_per_layer=round(bpl, 4),
            reasoning="; ".join(reasoning_parts),
            fits_vram=bool(ok_vram),
            fits_ram=bool(ok_ram),
            fallback_chain=["full_gpu", "partial_gpu", "cpu"] if use_gpu else ["cpu"],
        )

        logger.info(
            "Router plan: ctx=%d gpu=%s ngl=%d batch=%d | %s",
            strategy.n_ctx, strategy.use_gpu, strategy.n_gpu_layers,
            strategy.batch_size, strategy.reasoning,
        )
        return strategy

    def plan_with_overrides(
        self, profile: ModelProfile, *,
        n_ctx: Optional[int] = None,
        use_gpu: Optional[bool] = None,
        n_gpu_layers: Optional[int] = None,
    ) -> LoadStrategy:
        """Re-plan after a user override, recomputing fits for the new ctx.

        The auto plan picks ctx/layers; this applies a user's explicit
        choice and reports whether the result actually fits.
        """
        s = self.plan(profile)
        if n_ctx is not None:
            s.n_ctx = int(n_ctx)
        if use_gpu is not None:
            s.use_gpu = bool(use_gpu)
        if n_gpu_layers is not None:
            s.n_gpu_layers = int(n_gpu_layers)
        if not s.use_gpu:
            s.n_gpu_layers = 0
        ok_ram, ok_vram, _ = self._ctx_fits(profile, self._system, s.n_ctx)
        s.fits_vram = bool(ok_vram)
        s.fits_ram = bool(ok_ram)
        return s

    # ------------------------------------------------------------------
    # Adaptive helpers
    # ------------------------------------------------------------------

    def _ctx_fits(
        self, profile: ModelProfile, sys: SystemProfile, n_ctx: int
    ) -> Tuple[bool, bool, float]:
        """(ok_ram, ok_vram, kv_gb) for a candidate context size."""
        _, kv_gb, _ = _estimate_memory_detailed(
            profile.model_memory_gb, profile.total_layers, n_ctx,
            getattr(profile, "kv_heads", None),
            getattr(profile, "head_dim", None) or 128,
        )
        total = profile.model_memory_gb + kv_gb
        ok_ram = (sys.ram_gb <= 0) or (total <= sys.ram_gb * RAM_HEADROOM)
        ok_vram = False
        if sys.has_gpu_support and sys.vram_gb > 0:
            ok_vram = total + CUDA_RESERVE_GB <= sys.vram_gb
        return ok_ram, ok_vram, kv_gb

    def _optimal_context(self, profile: ModelProfile, sys: SystemProfile) -> int:
        """Largest ctx from the canonical options that fits RAM (and, above
        8192, also fits reserve-aware VRAM on GPU systems).

        Never blindly returns min(trained_context, 32768): on a small GPU
        that context may not even fit in RAM once KV is counted.
        """
        cap = profile.trained_context if profile.trained_context > 0 else 32768
        for cand in sorted(CTX_OPTIONS, reverse=True):
            if cand > cap:
                continue
            ok_ram, ok_vram, _ = self._ctx_fits(profile, sys, cand)
            if not ok_ram:
                continue
            if not (sys.has_gpu_support and sys.vram_gb > 0):
                return cand
            if ok_vram or cand <= 8192:
                return cand
        return 2048

    def _optimal_batch(self, profile: ModelProfile, sys: SystemProfile,
                       n_ctx: int = 0) -> int:
        """Canonical batch: 512 default; 256 on long ctx or tiny VRAM;
        1024 only for giant models on big GPUs."""
        if profile.size_tier in (SizeTier.XXLARGE, SizeTier.MEGA) and sys.vram_gb >= 16:
            return 1024
        if n_ctx >= 16384 or (sys.vram_gb > 0 and sys.vram_gb < 6):
            return 256
        return 512

    # ------------------------------------------------------------------
    # Role-based routing
    # ------------------------------------------------------------------

    def route(self, profile: ModelProfile, role: ModelRole) -> RoleConfig:
        """Get sampling parameters tuned for a specific role.

        The role config layers on top of:
          1. Family defaults (from model_profiles.py)
          2. User overrides (from model_params.json)
          3. Role-specific adjustments
        """
        base = dict(profile.family_params)
        role_config = _ROLE_DEFAULTS.get(role, _ROLE_DEFAULTS[ModelRole.CHAT])

        # Start with family params, apply role overrides
        merged = RoleConfig(
            role=role,
            temperature=base.get("temperature", role_config.temperature),
            top_k=base.get("top_k", role_config.top_k),
            top_p=base.get("top_p", role_config.top_p),
            min_p=base.get("min_p", role_config.min_p),
            repeat_penalty=base.get("repeat_penalty", role_config.repeat_penalty),
            max_tokens=base.get("max_tokens", role_config.max_tokens),
            system_prompt=base.get("system_prompt") or role_config.system_prompt,
            task_prompts=base.get("task_prompts", {}),
            notes=role_config.notes,
        )

        # Role-specific adjustments
        if role == ModelRole.AGENT:
            # Agent needs structured output — lower temperature, more deterministic
            merged.temperature = min(merged.temperature, 0.3)
            merged.top_k = min(merged.top_k, 40)
            merged.repeat_penalty = max(merged.repeat_penalty, 1.1)
            merged.notes = "Agent mode: low temperature for reliable JSON output"

        elif role == ModelRole.CODE:
            # Code generation benefits from higher creativity
            merged.temperature = max(merged.temperature, 0.4)
            merged.repeat_penalty = 1.0  # code has natural repetition
            merged.notes = "Code mode: moderate temperature, reduced repetition penalty"

        elif role == ModelRole.REASONING:
            # Thinking models need room to reason
            merged.temperature = 0.6  # not too high, not too low
            merged.top_k = 40
            merged.notes = "Reasoning mode: balanced for chain-of-thought"

        elif role == ModelRole.EMBED:
            # Embedding models don't use sampling
            merged.temperature = 0.0
            merged.notes = "Embedding mode: deterministic"

        elif role == ModelRole.CHAT:
            merged.notes = "Chat mode: family defaults"

        elif role == ModelRole.MULTIMODAL:
            merged.temperature = max(merged.temperature, 0.5)
            merged.notes = "Multimodal: moderate temperature for vision tasks"

        # Cap max_tokens to trained context (with safety margin)
        if profile.trained_context > 0 and merged.max_tokens > profile.trained_context - 256:
            merged.max_tokens = max(256, profile.trained_context - 256)

        # Thinking models get larger token budgets
        if profile.is_thinking_model and role in (ModelRole.CHAT, ModelRole.REASONING):
            merged.max_tokens = max(merged.max_tokens, 16384)
            merged.notes += " (thinking model — extended token budget)"

        logger.debug(
            "Router route: role=%s temp=%.2f top_k=%d max_tokens=%d | %s",
            role.value, merged.temperature, merged.top_k,
            merged.max_tokens, merged.notes,
        )
        return merged

    # ------------------------------------------------------------------
    # Convenience: inspect + plan + load
    # ------------------------------------------------------------------

    def load(
        self,
        path: str,
        role: ModelRole = ModelRole.CHAT,
        *,
        n_ctx: Optional[int] = None,
        use_gpu: Optional[bool] = None,
        n_gpu_layers: Optional[int] = None,
    ) -> Tuple["ModelBackend", ModelProfile, LoadStrategy, RoleConfig]:
        """Inspect → plan → load. Returns (backend, profile, strategy, config).

        The router decides: it picks the strategy (honoring any explicit
        overrides) and walks the fallback ladder full → partial → CPU, so
        ModelBackend stays a pure executor. Every attempt is recorded on
        ``strategy.attempts``.
        """
        from ggufloader.core.llm.model_backend import ModelBackend

        profile = self.inspect(path)
        if any(v is not None for v in (n_ctx, use_gpu, n_gpu_layers)):
            strategy = self.plan_with_overrides(
                profile, n_ctx=n_ctx, use_gpu=use_gpu, n_gpu_layers=n_gpu_layers)
        else:
            strategy = self.plan(profile)

        config = self.route(profile, role)

        logger.info(
            "Router load: %s role=%s ctx=%d gpu=%s ngl=%d",
            profile.filename, role.value, strategy.n_ctx,
            strategy.use_gpu, strategy.n_gpu_layers,
        )

        # --- Fallback ladder: full → partial → CPU (small ctx, no FA) ---
        attempts: List[str] = []
        ladder = self._load_ladder(strategy, profile)
        last_err: Optional[Exception] = None
        for desc, kwargs in ladder:
            try:
                backend = ModelBackend(
                    path,
                    use_gpu=kwargs["use_gpu"],
                    n_ctx=kwargs["n_ctx"],
                    n_gpu_layers=kwargs["n_gpu_layers"],
                    n_batch=strategy.batch_size,
                    n_threads=strategy.n_threads,
                    n_keep=512,
                    flash_attn=kwargs.get("flash_attn", strategy.flash_attn),
                    use_mmap=strategy.use_mmap,
                    rope_freq_base=strategy.rope_freq_base,
                )
                backend.load()
                attempts.append(desc)
                strategy.attempts = attempts
                return backend, profile, strategy, config
            except Exception as e:  # noqa: BLE001 - any attempt may fail
                attempts.append(desc)
                last_err = e
                logger.warning(
                    "Router load attempt '%s' failed for %s: %s",
                    desc, path, e,
                )

        strategy.attempts = attempts
        suggestion = (
            "Try a Q3/Q4 quantization, a smaller context (4096), or CPU-only mode."
            if strategy.use_gpu
            else "The model file may be corrupt or unsupported."
        )
        raise RuntimeError(
            f"Could not load {profile.filename} after {len(attempts)} attempt(s) "
            f"({', '.join(attempts)}). Last error: {last_err}. {suggestion}"
        )

    def _load_ladder(
        self, strategy: LoadStrategy, profile: ModelProfile
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Ordered attempts: full → partial → CPU-small-ctx."""
        if not strategy.use_gpu:
            return [(
                "cpu",
                {"use_gpu": False, "n_ctx": strategy.n_ctx, "n_gpu_layers": 0},
            )]
        steps: List[Tuple[str, Dict[str, Any]]] = []
        full_ngl = strategy.n_gpu_layers
        steps.append((
            "full_gpu",
            {"use_gpu": True, "n_ctx": strategy.n_ctx, "n_gpu_layers": full_ngl},
        ))
        total = profile.total_layers or 0
        if total > 0:
            base = total if full_ngl == -1 else min(full_ngl, total)
            partial_ngl = max(1, base // 2)
            if partial_ngl < (total if full_ngl == -1 else full_ngl):
                steps.append((
                    "partial_gpu",
                    {"use_gpu": True, "n_ctx": strategy.n_ctx,
                     "n_gpu_layers": partial_ngl},
                ))
        steps.append((
            "cpu",
            {"use_gpu": False, "n_ctx": min(strategy.n_ctx, 8192),
             "n_gpu_layers": 0, "flash_attn": False},
        ))
        return steps

    # ------------------------------------------------------------------
    # Model switching
    # ------------------------------------------------------------------

    def suggest_role(self, profile: ModelProfile) -> ModelRole:
        """Auto-suggest the best role for a model based on its profile."""
        if profile.is_embedding_model:
            return ModelRole.EMBED
        if profile.is_thinking_model:
            return ModelRole.REASONING
        if profile.supports_vision:
            return ModelRole.MULTIMODAL
        if _is_code_model(profile):
            return ModelRole.CODE
        return ModelRole.CHAT

    def can_serve_role(self, profile: ModelProfile, role: ModelRole) -> bool:
        """Check if a model is suitable for a given role."""
        if role == ModelRole.EMBED:
            return profile.is_embedding_model
        if role == ModelRole.MULTIMODAL:
            return profile.supports_vision
        if role == ModelRole.CODE:
            return not profile.is_embedding_model
        # Chat, Agent, Reasoning all work with any instruct model
        return not profile.is_embedding_model

    def quick_profile(self, path: str) -> Dict[str, Any]:
        """Fast, lightweight profile — just enough for a file picker / catalog.

        Unlike inspect(), this doesn't compute memory estimates or
        deep template analysis. Suitable for listing many models.
        """
        p = Path(path)
        meta = _read_gguf_metadata(p)
        arch = (meta.get("architecture") or "").lower()
        name = meta.get("name", "")
        file_gb = p.stat().st_size / (1024 ** 3) if p.exists() else 0

        from ggufloader.core.llm.model_profiles import detect_family
        family_profile, detected_via = detect_family(meta, path)

        return {
            "path": str(p),
            "filename": p.name,
            "file_size_gb": round(file_gb, 2),
            "architecture": arch,
            "family": family_profile.get("family", "generic"),
            "family_label": family_profile.get("label", "Generic"),
            "detected_via": detected_via,
            "size_tier": _size_tier_from_gb(file_gb).value,
            "param_estimate": _param_estimate_from_filename(p.name) or _param_estimate_from_size(file_gb),
            "is_embedding": _is_embedding_model(arch, name, meta.get("basename", "")),
            "is_vision": _is_vision_model(arch, name, meta.get("basename", ""), meta),
        }


# ---------------------------------------------------------------------------
# Role defaults
# ---------------------------------------------------------------------------

_ROLE_DEFAULTS: Dict[ModelRole, RoleConfig] = {
    ModelRole.CHAT: RoleConfig(
        role=ModelRole.CHAT,
        temperature=0.7, top_k=40, top_p=0.9, min_p=0.0,
        repeat_penalty=1.05, max_tokens=4096,
    ),
    ModelRole.AGENT: RoleConfig(
        role=ModelRole.AGENT,
        temperature=0.2, top_k=40, top_p=0.9, min_p=0.0,
        repeat_penalty=1.1, max_tokens=2048,
        notes="Agent mode: structured JSON output",
    ),
    ModelRole.CODE: RoleConfig(
        role=ModelRole.CODE,
        temperature=0.5, top_k=40, top_p=0.95, min_p=0.0,
        repeat_penalty=1.0, max_tokens=4096,
        notes="Code generation",
    ),
    ModelRole.EMBED: RoleConfig(
        role=ModelRole.EMBED,
        temperature=0.0, top_k=0, top_p=1.0, min_p=0.0,
        repeat_penalty=1.0, max_tokens=0,
        notes="Embedding (no sampling)",
    ),
    ModelRole.REASONING: RoleConfig(
        role=ModelRole.REASONING,
        temperature=0.6, top_k=40, top_p=0.9, min_p=0.0,
        repeat_penalty=1.05, max_tokens=16384,
        notes="Chain-of-thought reasoning",
    ),
    ModelRole.MULTIMODAL: RoleConfig(
        role=ModelRole.MULTIMODAL,
        temperature=0.5, top_k=40, top_p=0.9, min_p=0.0,
        repeat_penalty=1.05, max_tokens=4096,
        notes="Vision/multimodal tasks",
    ),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# -- GGUF metadata reading (minimal, no tensor access) --

# Single shared reader lives in core/llm/gguf_meta.py; keep the name so
# existing callers (inspect/quick_profile) keep working unchanged.
from ggufloader.core.llm.gguf_meta import read as _read_gguf_metadata  # noqa: E402


def _extract_uint(meta: Dict, arch: str, suffix: str) -> int:
    """Extract a uint32/uint64 value like '<arch>.context_length'."""
    for k, v in meta.items():
        if k.endswith(f".{suffix}") and isinstance(v, (int, float)):
            return int(v)
    return 0


def _extract_layers(meta: Dict, arch: str) -> int:
    """Extract total layer count from metadata."""
    return _extract_uint(meta, arch, "block_count")


# -- Size / quantization detection --

def _size_tier_from_gb(gb: float) -> SizeTier:
    if gb <= 1.0:
        return SizeTier.TINY
    if gb <= 3.0:
        return SizeTier.SMALL
    if gb <= 6.0:
        return SizeTier.MEDIUM
    if gb <= 10.0:
        return SizeTier.LARGE
    if gb <= 20.0:
        return SizeTier.XLARGE
    if gb <= 45.0:
        return SizeTier.XXLARGE
    return SizeTier.MEGA


# Filename patterns for param count extraction (order matters — most specific first)
_PARAM_RE = re.compile(
    r"(\d+\.?\d*)\s*[BbMm]"
    r"|[-_](\d+)(?:b|B)"
    r"|[-_](7|8|13|14|20|30|34|40|65|70|72|110|120|180|405)(?:b|B)",
)


def _param_estimate_from_filename(name: str) -> str:
    """Extract param count string from filename like 'Qwen3-8B' → '8B'."""
    # Try common patterns: "7B", "13B", "8B-Instruct", etc.
    name_clean = name.replace("_", "-")
    m = re.search(r"[-_](\d+\.?\d*)[Bb](?:[-_]|\.|$)", name_clean)
    if m:
        val = float(m.group(1))
        if val >= 1:
            return f"{int(val)}B" if val == int(val) else f"{val}B"
    # Try "72b" at end
    m = re.search(r"[-_](\d+)[Bb](?:\.gguf)?$", name_clean)
    if m:
        return f"{m.group(1)}B"
    return ""


def _param_estimate_from_size(gb: float) -> str:
    """Rough param count from file size (assumes Q4 quantization ~0.6 GB/B params)."""
    if gb <= 0:
        return ""
    # Q4 is ~0.6 GB per billion params; F16 is ~2 GB/B
    params_q4 = gb / 0.6
    params_f16 = gb / 2.0
    # Pick the closest standard tier
    for tier in [0.5, 1, 3, 7, 8, 13, 14, 20, 30, 34, 40, 65, 70, 72, 110]:
        if params_q4 <= tier * 1.3:
            return f"{int(tier)}B" if tier == int(tier) else f"{tier}B"
    return f"{int(params_q4)}B"


_QUANT_TIERS = {
    "q2": QuantTier.LOW, "iq2": QuantTier.LOW,
    "q3": QuantTier.MEDIUM, "iq3": QuantTier.MEDIUM,
    "q4": QuantTier.GOOD, "iq4": QuantTier.GOOD,
    "q5": QuantTier.HIGH, "iq5": QuantTier.HIGH,
    "q6": QuantTier.VERY_HIGH,
    "q8": QuantTier.VERY_HIGH,
    "f16": QuantTier.FULL, "f32": QuantTier.FULL,
}


def _detect_quantization(filename: str, meta: Dict) -> Tuple[str, QuantTier]:
    """Detect quantization from filename + metadata."""
    name_lower = filename.lower()
    # Try filename patterns
    for pattern in ["iq4_xs", "iq4_xl", "iq3_xxs", "iq3_xs", "iq3_x",
                     "iq2_xxs", "iq2_xs", "iq2_x",
                     "q8_0", "q6_k", "q5_k_m", "q5_k_s", "q5_0",
                     "q4_k_m", "q4_k_s", "q4_0", "q4_1",
                     "q3_k_m", "q3_k_s", "q3_k_l", "q3_0",
                     "q2_k", "q2_0",
                     "f16", "f32"]:
        if pattern in name_lower:
            tier = QuantTier.GOOD  # default
            for prefix, t in _QUANT_TIERS.items():
                if pattern.startswith(prefix):
                    tier = t
                    break
            return pattern.upper(), tier

    # Metadata fallback
    quant_ver = meta.get("general.quantization_version")
    if quant_ver:
        return str(quant_ver), QuantTier.GOOD

    return "", QuantTier.GOOD


# -- Capability detection --

def _is_embedding_model(arch: str, name: str, basename: str) -> bool:
    embed_archs = {"nomic-bert", "bert", "jina-bert", "jina-bert-v2", "snowflake-arctic-embed"}
    name_blob = f"{name} {basename}".lower()
    return arch in embed_archs or "embed" in name_blob


def _is_vision_model(arch: str, name: str, basename: str, meta: Dict) -> bool:
    """Detect vision/multimodal models."""
    vision_archs = {"llava", "bakllava", "moondream", "obsidian", "nanollava",
                    "mobilevlm", "llama-4", "gemma3"}
    name_blob = f"{name} {basename}".lower()
    return (
        arch in vision_archs
        or "vision" in name_blob
        or "vl" in name_blob
        or "llava" in name_blob
    )


def _is_thinking_model(arch: str, name: str, filename: str) -> bool:
    """Detect chain-of-thought / reasoning models."""
    name_blob = f"{name} {filename}".lower()
    thinking_markers = ["r1", "reason", "think", "deepseek-r1", "qwq", "o1", "o3"]
    return any(m in name_blob for m in thinking_markers)


def _is_code_model(profile: ModelProfile) -> bool:
    """Heuristic: is this primarily a code model?"""
    name = profile.filename.lower()
    code_markers = ["code", "coder", "starcoder", "codellama", "deepseek-coder",
                    "qwen2.5-coder", "wizard-coder", "CodeGemma"]
    return any(m in name for m in code_markers)


# -- Memory estimation --

def _estimate_memory_detailed(
    file_size_gb: float, layers: int, n_ctx: int,
    kv_heads: Optional[int] = None, head_dim: Optional[int] = None,
) -> Tuple[float, float, float]:
    """Estimate model + KV cache memory in GB, plus bytes-per-layer.

    GQA-aware: KV bytes = n_ctx * 2 (K+V) * layers * kv_heads * head_dim *
    2 bytes (fp16). Falls back to 8 kv heads / 128 head dim when the GGUF
    header did not expose them.
    """
    model_gb = file_size_gb  # GGUF file size ≈ model weights

    if layers and layers > 0:
        kv_heads_eff = kv_heads or 8
        head_dim_eff = head_dim or 128
        kv_bytes = n_ctx * 2 * layers * kv_heads_eff * head_dim_eff * 2
        kv_gb = kv_bytes / (1024 ** 3)
        bpl = file_size_gb / layers
    else:
        kv_gb = model_gb * 0.2 * (n_ctx / 32768)
        bpl = 0.0

    return model_gb, kv_gb, bpl


def _fits_in_vram(profile: ModelProfile, use_gpu: bool) -> bool:
    if not use_gpu:
        return False
    sys = SystemProfile.detect()
    return profile.model_memory_gb <= sys.vram_gb * 0.85


def _fits_in_ram(profile: ModelProfile) -> bool:
    sys = SystemProfile.detect()
    return profile.total_memory_gb <= sys.ram_gb * 0.85


# -- System detection --

def _get_ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass
    try:
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            return mem.ullTotalPhys / (1024 ** 3)
        else:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) / (1024 ** 2)
    except Exception:
        pass
    return 0.0


def _get_vram_info() -> Tuple[float, str]:
    """Get GPU VRAM and name via nvidia-smi."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=memory.total,name",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if lines:
                parts = lines[0].split(", ")
                vram_mb = float(parts[0].strip())
                gpu_name = parts[1].strip() if len(parts) > 1 else ""
                return vram_mb / 1024, gpu_name
    except Exception:
        pass
    return 0.0, ""


def _check_gpu_support() -> bool:
    """Check if llama-cpp-python was compiled with GPU support."""
    return llama_supports_gpu_offload()


def _detect_gpu_backend() -> str:
    """Detect which GPU backend llama.cpp is using."""
    if llama_supports_gpu_offload():
        if platform.system() == "Darwin":
            return "metal"
        return "cuda"
    if llama_supports_metal():
        return "metal"
    if platform.system() == "Darwin":
        # macOS — Metal is always available if compiled
        return "metal"
    return ""
