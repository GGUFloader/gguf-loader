from __future__ import annotations

import re
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


_FAMILY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("gemma4", re.compile(r"gemma[-_]?4|gemma4", re.IGNORECASE)),
    ("gemma3", re.compile(r"gemma[-_]?3|gemma3", re.IGNORECASE)),
    ("qwen2.5", re.compile(r"qwen2\.?5|qwen[-_]?2\.?5", re.IGNORECASE)),
    ("llama3", re.compile(r"llama[-_]?3|llama3", re.IGNORECASE)),
    ("phi3", re.compile(r"phi[-_]?3|phi3", re.IGNORECASE)),
    ("mistral", re.compile(r"mistral|mixtral", re.IGNORECASE)),
]


def _detect_family(model_path: str | Path) -> str:
    name = Path(model_path).stem.lower()
    for family, pat in _FAMILY_PATTERNS:
        if pat.search(name):
            return family
    return "default"


def _clamp_ctx(n_ctx_train: int, target: int) -> int:
    if n_ctx_train <= 0:
        return target
    return min(target, n_ctx_train)


def _make_profile(family: str, n_ctx_train: int) -> ModelProfile:
    if family == "gemma4":
        n_ctx = _clamp_ctx(n_ctx_train, 8192)
        return ModelProfile(
            max_tokens=4096, max_steps=20, temperature=0.1,
            n_ctx_target=n_ctx, n_batch=512, n_threads=8, n_keep=512,
            use_mmap=True, flash_attn=True, json_retries=2,
        )
    if family == "gemma3":
        n_ctx = _clamp_ctx(n_ctx_train, 8192)
        return ModelProfile(
            max_tokens=4096, max_steps=16, temperature=0.1,
            n_ctx_target=n_ctx, n_batch=512, n_threads=8, n_keep=512,
            use_mmap=True, flash_attn=True, json_retries=2,
        )
    if family == "qwen2.5":
        n_ctx = _clamp_ctx(n_ctx_train, 16384)
        return ModelProfile(
            max_tokens=4096, max_steps=20, temperature=0.1,
            n_ctx_target=n_ctx, n_batch=1024, n_threads=8, n_keep=512,
            use_mmap=True, flash_attn=True, json_retries=2,
        )
    if family == "llama3":
        n_ctx = _clamp_ctx(n_ctx_train, 8192)
        return ModelProfile(
            max_tokens=4096, max_steps=20, temperature=0.1,
            n_ctx_target=n_ctx, n_batch=512, n_threads=8, n_keep=512,
            use_mmap=True, flash_attn=True, json_retries=2,
        )
    if family == "phi3":
        n_ctx = _clamp_ctx(n_ctx_train, 4096)
        return ModelProfile(
            max_tokens=2048, max_steps=12, temperature=0.1,
            n_ctx_target=n_ctx, n_batch=256, n_threads=8, n_keep=256,
            use_mmap=True, flash_attn=True, json_retries=3,
        )
    if family == "mistral":
        n_ctx = _clamp_ctx(n_ctx_train, 8192)
        return ModelProfile(
            max_tokens=4096, max_steps=20, temperature=0.1,
            n_ctx_target=n_ctx, n_batch=512, n_threads=8, n_keep=512,
            use_mmap=True, flash_attn=True, json_retries=2,
        )
    n_ctx = _clamp_ctx(n_ctx_train, 8192)
    return ModelProfile(
        max_tokens=4096, max_steps=16, temperature=0.1,
        n_ctx_target=n_ctx, n_batch=512, n_threads=8, n_keep=512,
        use_mmap=True, flash_attn=True, json_retries=2,
    )


AGENT_PROFILE_REGISTRY: dict[str, ModelProfile] = {
    "gemma4": _make_profile("gemma4", 8192),
    "gemma3": _make_profile("gemma3", 8192),
    "qwen2.5": _make_profile("qwen2.5", 16384),
    "llama3": _make_profile("llama3", 8192),
    "phi3": _make_profile("phi3", 4096),
    "mistral": _make_profile("mistral", 8192),
    "default": _make_profile("default", 8192),
}


def get_profile(model_path: str | Path, n_ctx_train: int = 0) -> ModelProfile:
    family = _detect_family(model_path)
    if family == "default" and n_ctx_train > 0:
        return _make_profile("default", n_ctx_train)
    if family in AGENT_PROFILE_REGISTRY and n_ctx_train <= 0:
        return AGENT_PROFILE_REGISTRY[family]
    return _make_profile(family, n_ctx_train)