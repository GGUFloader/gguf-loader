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
import struct
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    n_ctx: int = 16384
    n_gpu_layers: int = -1         # -1 = auto (all layers)
    use_gpu: bool = False
    batch_size: int = 512
    rope_freq_base: Optional[float] = None
    reasoning: str = ""            # human explanation of choices

    # Memory fit
    fits_vram: bool = False
    fits_ram: bool = False
    fallback_chain: List[str] = field(default_factory=list)  # what was tried


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
        self._profile_cache: Dict[str, ModelProfile] = {}  # path → cached profile

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

        # Return cached profile if available
        cache_key = str(p.resolve())
        if cache_key in self._profile_cache:
            return self._profile_cache[cache_key]

        file_size_gb = p.stat().st_size / (1024 ** 3)

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

        # Memory estimates
        model_gb, kv_gb = _estimate_memory_detailed(
            file_size_gb, total_layers, max_ctx or 32768
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
                         "min_p", "max_tokens")
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
        """Determine the optimal loading strategy for this model on this system."""
        sys = self._system
        strategy = LoadStrategy()

        # --- GPU decision ---
        use_gpu = False
        n_gpu_layers = 0
        reasoning_parts = []

        if profile.is_embedding_model:
            # Embedding models are small; CPU is fine
            reasoning_parts.append("Embedding model — CPU preferred for quick load/unload")
            use_gpu = False
            n_gpu_layers = 0
        elif sys.has_gpu_support and sys.vram_gb > 0:
            # Check if model fits in VRAM
            if profile.model_memory_gb <= sys.vram_gb * 0.85:
                use_gpu = True
                n_gpu_layers = -1  # all layers
                reasoning_parts.append(
                    f"Model ({profile.model_memory_gb:.1f} GB) fits in VRAM "
                    f"({sys.vram_gb:.1f} GB) — full GPU offload"
                )
            elif profile.model_memory_gb <= sys.vram_gb * 1.2:
                # Partial offload — estimate how many layers fit
                if profile.total_layers > 0:
                    vram_ratio = (sys.vram_gb * 0.85) / profile.model_memory_gb
                    n_gpu_layers = max(1, int(profile.total_layers * vram_ratio))
                    use_gpu = True
                    reasoning_parts.append(
                        f"Partial GPU offload: {n_gpu_layers}/{profile.total_layers} "
                        f"layers ({vram_ratio:.0%} of model fits in VRAM)"
                    )
                else:
                    use_gpu = True
                    n_gpu_layers = -1
                    reasoning_parts.append(
                        f"Attempting full offload (layers unknown); GPU ladder will adjust"
                    )
            else:
                # Model too large for VRAM — try CPU
                reasoning_parts.append(
                    f"Model ({profile.model_memory_gb:.1f} GB) exceeds VRAM "
                    f"({sys.vram_gb:.1f} GB) — CPU mode"
                )
        else:
            reasoning_parts.append("No GPU support — CPU mode")

        # --- Context size ---
        n_ctx = self._optimal_context(profile, sys)
        if n_ctx != 32768:
            reasoning_parts.append(f"Context set to {n_ctx} (optimized for model + system)")

        # --- Batch size ---
        batch = self._optimal_batch(profile, sys)

        strategy = LoadStrategy(
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            use_gpu=use_gpu,
            batch_size=batch,
            reasoning="; ".join(reasoning_parts),
            fits_vram=self._check_fits_vram(profile, use_gpu),
            fits_ram=self._check_fits_ram(profile),
            fallback_chain=["full_gpu", "half_gpu", "cpu"] if use_gpu else ["cpu"],
        )

        logger.info(
            "Router plan: ctx=%d gpu=%s ngl=%d batch=%d | %s",
            strategy.n_ctx, strategy.use_gpu, strategy.n_gpu_layers,
            strategy.batch_size, strategy.reasoning,
        )
        return strategy

    # ------------------------------------------------------------------
    # Adaptive helpers
    # ------------------------------------------------------------------

    def _optimal_context(self, profile: ModelProfile, sys: SystemProfile) -> int:
        """Choose the best context size for this model + system."""
        # If the model declares a trained context, respect it
        if profile.trained_context > 0:
            # Don't go above trained context (degrades quality)
            return min(profile.trained_context, 32768)
        # Memory-aware: fit model + KV within available RAM
        # KV at 32K context is ~20% of model size (heuristic)
        kv_at_32k = profile.model_memory_gb * 0.2
        if profile.model_memory_gb + kv_at_32k > sys.ram_gb * 0.8 and sys.ram_gb > 0:
            # Scale down context proportionally
            ratio = (sys.ram_gb * 0.8 - profile.model_memory_gb) / max(kv_at_32k, 0.01)
            ratio = max(0.1, min(1.0, ratio))
            return max(512, int(32768 * ratio))
        return 32768

    def _optimal_batch(self, profile: ModelProfile, sys: SystemProfile) -> int:
        """Choose batch size. Larger models and more RAM → larger batch."""
        if profile.size_tier in (SizeTier.TINY, SizeTier.SMALL):
            return 256
        if profile.size_tier in (SizeTier.LARGE, SizeTier.XLARGE):
            return 512
        if profile.size_tier in (SizeTier.XXLARGE, SizeTier.MEGA):
            return 1024
        return 512

    def _check_fits_vram(self, profile: ModelProfile, use_gpu: bool) -> bool:
        if not use_gpu:
            return False
        return profile.model_memory_gb <= self._system.vram_gb * 0.85

    def _check_fits_ram(self, profile: ModelProfile) -> bool:
        return profile.total_memory_gb <= self._system.ram_gb * 0.85

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
            system_prompt=role_config.system_prompt,
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

        Caller can override any plan parameter (n_ctx, use_gpu, n_gpu_layers).
        """
        from ggufloader.core.llm.model_backend import ModelBackend

        profile = self.inspect(path)
        strategy = self.plan(profile)

        # Apply overrides
        if n_ctx is not None:
            strategy.n_ctx = n_ctx
        if use_gpu is not None:
            strategy.use_gpu = use_gpu
        if n_gpu_layers is not None:
            strategy.n_gpu_layers = n_gpu_layers

        config = self.route(profile, role)

        logger.info(
            "Router load: %s role=%s ctx=%d gpu=%s ngl=%d",
            profile.filename, role.value, strategy.n_ctx,
            strategy.use_gpu, strategy.n_gpu_layers,
        )

        backend = ModelBackend(
            path,
            use_gpu=strategy.use_gpu,
            n_ctx=strategy.n_ctx,
            n_gpu_layers=strategy.n_gpu_layers,
        )
        backend.load()

        return backend, profile, strategy, config

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

_GGUF_MAGIC = b"GGUF"
_TYPES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_T_STRING, _T_ARRAY = 8, 9


def _read_str(f) -> str:
    (n,) = struct.unpack("<Q", f.read(8))
    return f.read(n).decode("utf-8", errors="replace")


def _skip_value(f, vtype: int) -> Any:
    if vtype == _T_STRING:
        return _read_str(f)
    if vtype == _T_ARRAY:
        (etype,) = struct.unpack("<I", f.read(4))
        (count,) = struct.unpack("<Q", f.read(8))
        if etype == _T_STRING:
            for _ in range(count):
                _read_str(f)
            return None
        size = _TYPES.get(etype)
        if size is None:
            return None
        f.seek(count * size, 1)
        return None
    size = _TYPES.get(vtype)
    if size is None:
        return None
    raw = f.read(size)
    if vtype in (4, 10):
        return struct.unpack("<Q" if vtype == 10 else "<I", raw)[0]
    if vtype in (5, 11):
        return struct.unpack("<q" if vtype == 11 else "<i", raw)[0]
    if vtype == 6:
        return struct.unpack("<f", raw)[0]
    if vtype == 12:
        return struct.unpack("<d", raw)[0]
    if vtype == 7:
        return raw[0] != 0
    return raw[0] if raw else None


def _read_gguf_metadata(path: Path, max_bytes: int = 8 * 1024 * 1024) -> Dict[str, Any]:
    """Read GGUF header metadata (architecture, name, context_length, etc.)."""
    out: Dict[str, Any] = {}
    try:
        with open(path, "rb") as f:
            if f.read(4) != _GGUF_MAGIC:
                return {}
            (version,) = struct.unpack("<I", f.read(4))
            if version not in (2, 3):
                return {}
            struct.unpack("<Q", f.read(8))  # tensor count
            (kv_count,) = struct.unpack("<Q", f.read(8))
            for _ in range(kv_count):
                if f.tell() > max_bytes:
                    break
                key = _read_str(f)
                (vtype,) = struct.unpack("<I", f.read(4))

                # Capture general.* strings
                if key.startswith("general.") and vtype == _T_STRING:
                    out[key[len("general."):]] = _read_str(f)
                # Capture chat template
                elif key == "tokenizer.chat_template" and vtype == _T_STRING:
                    out["chat_template"] = _read_str(f)
                # Capture context_length / block_count
                elif vtype in (4, 10) and (
                    key.endswith(".context_length") or key.endswith(".block_count")
                ):
                    out[key] = _skip_value(f, vtype)
                else:
                    _skip_value(f, vtype)
    except Exception as e:
        logger.debug("GGUF metadata read failed for %s: %s", path, e)
    return out


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
    file_size_gb: float, layers: int, n_ctx: int
) -> Tuple[float, float]:
    """Estimate model + KV cache memory in GB."""
    model_gb = file_size_gb  # GGUF file size ≈ model weights

    if layers > 0:
        head_dim = 128
        kv_per_layer = n_ctx * 2 * head_dim * 2  # bytes (key+value, float16)
        kv_gb = (layers * kv_per_layer) / (1024 ** 3)
    else:
        kv_gb = model_gb * 0.2 * (n_ctx / 32768)

    return model_gb, kv_gb


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
    try:
        from llama_cpp import llama_cpp as _lc
        probe = getattr(_lc, "llama_supports_gpu_offload", None)
        return bool(probe()) if callable(probe) else False
    except Exception:
        return False


def _detect_gpu_backend() -> str:
    """Detect which GPU backend llama.cpp is using."""
    try:
        from llama_cpp import llama_cpp as _lc
        # Check CUDA
        probe = getattr(_lc, "llama_supports_gpu_offload", None)
        if probe and callable(probe) and probe():
            if platform.system() == "Darwin":
                return "metal"
            return "cuda"
    except Exception:
        pass
    if platform.system() == "Darwin":
        # macOS — Metal is always available if compiled
        return "metal"
    return ""
