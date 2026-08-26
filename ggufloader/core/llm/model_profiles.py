"""Model-family detection and automatic chat configuration.

Reads a GGUF file's metadata header (pure Python, no model load - the
header sits before the tensor data) to identify the model family:

    general.architecture  e.g. "lfm2", "qwen3", "llama", "gemma3"
    general.name          e.g. "LFM2.5-8B-Instruct"
    general.basename      e.g. "LFM2.5-8B-Instruct"

and picks a matching profile: sampling parameters plus an optional
system-prompt suggestion. Filename substrings are the fallback when
metadata is missing/unreadable. The user's ``model_params.json``
overrides always win over the automatic profile.

Reference sources for per-family sampling: official model cards /
Ollama-baked parameters (LiquidAI LFM2.5: 0.2/80/1.05; Qwen3: 0.6/0.95/20;
Meta Llama-3.x: 0.6/0.9; DeepSeek-R1-Distill: 0.6/0.95;
Google Gemma-3: 1.0/0.95/64; gpt-oss: 1.0/1.0).
"""

from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Minimal GGUF metadata reader (v2/v3). Skips arrays/tensors cheaply.
# ---------------------------------------------------------------------------

_GGUF_MAGIC = b"GGUF"
_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_T_STRING, _T_ARRAY = 8, 9


def _read_str(f) -> str:
    (n,) = struct.unpack("<Q", f.read(8))
    return f.read(n).decode("utf-8", errors="replace")


def _skip_or_read(f, vtype: int, want: bool) -> Any:
    if vtype == _T_STRING:
        s = _read_str(f)
        return s if want else None
    if vtype == _T_ARRAY:
        (etype,) = struct.unpack("<I", f.read(4))
        (count,) = struct.unpack("<Q", f.read(8))
        if etype == _T_STRING:
            for _ in range(count):
                _read_str(f)
            return None
        size = _SIZES.get(etype)
        if size is None:  # nested arrays are illegal in GGUF; bail safely
            raise ValueError("nested array in GGUF metadata")
        f.seek(count * size, 1)
        return None
    size = _SIZES.get(vtype)
    if size is None:
        raise ValueError(f"unknown GGUF value type {vtype}")
    raw = f.read(size)
    if vtype == 4:  # uint32
        return struct.unpack("<I", raw)[0]
    if vtype == 5:  # int32
        return struct.unpack("<i", raw)[0]
    if vtype == 6:  # float32
        return struct.unpack("<f", raw)[0]
    if vtype == 12:  # float64
        return struct.unpack("<d", raw)[0]
    if vtype == 10:  # uint64
        return struct.unpack("<Q", raw)[0]
    if vtype == 11:  # int64
        return struct.unpack("<q", raw)[0]
    if vtype == 7:  # bool
        return raw[0] != 0
    return raw[0] if raw else None


def read_gguf_general_metadata(
    path: str | Path, max_bytes: int = 8 * 1024 * 1024
) -> Dict[str, Any]:
    """Return model metadata from the GGUF header (no tensor access).

    Collects every ``general.*`` string plus scalar ``<arch>.context_length``
    and ``<arch>.block_count`` entries (the arch prefix is unknown before
    parsing, hence suffix-matching). Raises nothing; returns {} for
    non-GGUF or unreadable files.
    """
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
                want_string = key.startswith("general.") and vtype == _T_STRING
                want_limit = (
                    vtype in (4, 10)  # uint32 / uint64
                    and (key.endswith(".context_length") or key.endswith(".block_count"))
                )
                if want_string:
                    out[key[len("general."):]] = _read_str(f)
                elif want_limit:
                    out[key] = _skip_or_read(f, vtype, False)
                else:
                    _skip_or_read(f, vtype, False)
    except Exception as e:  # noqa: BLE001 - any malformed file => no metadata
        logger.debug("GGUF metadata read failed for %s: %s", path, e)
    return out


def read_model_limits(path: str | Path) -> Dict[str, Optional[int]]:
    """``{"max_context": int|None, "layers": int|None}`` from GGUF metadata."""
    meta = read_gguf_general_metadata(path)
    ctx = next(
        (v for k, v in sorted(meta.items()) if k.endswith(".context_length")),
        None,
    )
    layers = next(
        (v for k, v in sorted(meta.items()) if k.endswith(".block_count")),
        None,
    )
    return {"max_context": ctx, "layers": layers}


# ---------------------------------------------------------------------------
# Family profiles
# ---------------------------------------------------------------------------

def _p(temperature: float, top_k: int, top_p: float,
       repeat_penalty: float = 1.05, min_p: float = 0.0) -> Dict[str, float]:
    return {
        "temperature": temperature,
        "top_k": top_k,
        "top_p": top_p,
        "repeat_penalty": repeat_penalty,
        "min_p": min_p,
    }


# Match order matters: first hit wins. `archs` matches the GGUF
# general.architecture string, `names` matches filename/metadata name.
FAMILY_PROFILES = [
    {
        "family": "liquid-lfm",
        "label": "LiquidAI LFM2",
        "archs": ("lfm2",),
        "names": ("lfm2", "lfm 2"),
        **_p(0.2, 80, 0.9, 1.05),
    },
    {
        "family": "qwen3",
        "label": "Qwen3",
        "archs": ("qwen3", "qwen3moe"),
        "names": ("qwen3",),
        **_p(0.6, 20, 0.95, 1.05),
    },
    {
        "family": "deepseek-r1",
        "label": "DeepSeek-R1 distill",
        "archs": (),
        "names": ("deepseek-r1", "r1-distill"),
        **_p(0.6, 40, 0.95, 1.1),
    },
    {
        "family": "llama3",
        "label": "Meta Llama 3.x",
        "archs": ("llama",),
        "names": ("llama-3", "llama3", "meta-llama-3"),
        **_p(0.6, 40, 0.9, 1.1),
    },
    {
        "family": "gemma3",
        "label": "Google Gemma 3",
        "archs": ("gemma3", "gemma2"),
        "names": ("gemma",),
        **_p(1.0, 64, 0.95, 1.05),
    },
    {
        "family": "gpt-oss",
        "label": "OpenAI gpt-oss",
        "archs": ("gpt_oss",),
        "names": ("gpt-oss", "gptoss"),
        **_p(1.0, 40, 1.0, 1.05),
    },
]

# Applied when nothing matches: conservative defaults that behave well on
# most small instruct quants (see the LFM2.5 degeneration incident).
GENERIC_PROFILE = {
    "family": "generic",
    "label": "Generic instruct",
    **_p(0.2, 80, 0.9, 1.05),
}


def detect_family(metadata: Dict[str, str], model_path: str | Path) -> Tuple[Dict[str, Any], str]:
    """Return ``(profile, how_detected)`` for the given model."""
    arch = (metadata.get("architecture") or "").lower()
    name = (
        metadata.get("name", "")
        + " "
        + metadata.get("basename", "")
        + " "
        + Path(str(model_path)).name.lower()
    )
    if arch:
        for prof in FAMILY_PROFILES:
            if any(a in arch for a in prof["archs"]):
                return prof, f"gguf arch '{arch}'"
    for prof in FAMILY_PROFILES:
        if any(n in name for n in prof["names"]):
            return prof, "filename match"
    return GENERIC_PROFILE, "no match"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def resolve_chat_config(model_path: str) -> Dict[str, Any]:
    """Full automatic chat configuration for a model.

    Returns ``{"family", "label", "detected_via", "params": {...},
    "system_prompt": None}``. Precedence: user's model_params.json >
    detected family profile > generic defaults.
    """
    from ggufloader.core.llm.model_params import load_model_params

    meta = read_gguf_general_metadata(model_path)
    profile, how = detect_family(meta, model_path)
    params = {k: v for k, v in profile.items()
              if k in ("temperature", "top_k", "top_p", "repeat_penalty", "min_p")}
    user = load_model_params(model_path)
    params.update(user)
    arch = (meta.get("architecture") or "").lower()
    name_blob = (meta.get("name", "") + " " + meta.get("basename", "")).lower()
    is_embedding_model = (
        arch in ("nomic-bert", "bert", "jina-bert", "jina-bert-v2")
        or "embed" in name_blob
    )
    return {
        "family": profile["family"],
        "label": profile.get("label", profile["family"]),
        "detected_via": how,
        "params": params,
        "system_prompt": None,
        "is_embedding_model": is_embedding_model,
        "meta": meta,
    }
