from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelProfile:
    max_tokens: int
    max_steps: int
    temperature: float
    n_ctx_target: int
    n_batch: int
    n_threads: int
    n_keep: int
    use_mmap: bool
    flash_attn: bool
    json_retries: int


# Single-model app: one profile for the pinned Gemma 4 12B Q4_K_M target.
# Multi-family detection and per-family registries were removed.
_TARGET = "gemma4"


def _clamp_ctx(n_ctx_train: int, target: int) -> int:
    if n_ctx_train <= 0:
        return target
    return min(target, n_ctx_train)


def _make_profile(family: str, n_ctx_train: int) -> ModelProfile:
    """Gemma 4 12B agent profile (sampling for reliable structured output)."""
    if family != _TARGET:
        family = _TARGET  # anything else is unsupported - use the target anyway
    n_ctx = _clamp_ctx(n_ctx_train, 8192)
    return ModelProfile(
        max_tokens=4096, max_steps=20, temperature=0.1,
        n_ctx_target=n_ctx, n_batch=512, n_threads=8, n_keep=512,
        use_mmap=True, flash_attn=True, json_retries=2,
    )


def get_profile(model_path: str | Path, n_ctx_train: int = 0) -> ModelProfile:
    """Return the pinned Gemma 4 agent profile for any model path.

    ``n_ctx_train`` (from GGUF metadata) clamps the context target when the
    file's trained context is smaller than the 8K agent target.
    """
    return _make_profile(_TARGET, n_ctx_train)
