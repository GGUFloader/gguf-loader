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

    Collects:
    - Every ``general.*`` string (architecture, name, etc.)
    - ``tokenizer.chat_template`` for template-based system prompt detection
    - Scalar ``<arch>.context_length`` and ``<arch>.block_count`` entries

    Raises nothing; returns {} for non-GGUF or unreadable files.
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
                # Read tokenizer.chat_template for template detection
                want_template = key == "tokenizer.chat_template" and vtype == _T_STRING
                want_limit = (
                    vtype in (4, 10)  # uint32 / uint64
                    and (key.endswith(".context_length") or key.endswith(".block_count"))
                )
                if want_string:
                    out[key[len("general."):]] = _read_str(f)
                elif want_template:
                    out["chat_template"] = _read_str(f)
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


def estimate_memory(path: str | Path, n_ctx: int = 32768,
                    n_gpu_layers: int = 0) -> Dict[str, Any]:
    """Estimate VRAM/RAM requirements for loading a model.

    Returns ``{"model_gb": float, "kv_gb": float, "total_gb": float,
    "fits_ram": bool, "fits_vram": bool, "layers": int|None,
    "quant": str|None}``.

    Heuristic: GGUF file size ≈ model weights in memory. KV cache is
    approximated as ``n_ctx × 2 × layers × head_dim × 2 bytes`` where
    head_dim defaults to 128 (typical for modern LLMs).
    """
    p = Path(path)
    file_size = p.stat().st_size if p.exists() else 0
    model_gb = file_size / (1024 ** 3)

    meta = read_gguf_general_metadata(p)
    layers = next(
        (v for k, v in sorted(meta.items()) if k.endswith(".block_count")),
        None,
    )
    quant = meta.get("general.quantization_version")
    # Try to detect quant from filename
    name_lower = p.name.lower()
    for q in ("q2_k", "q3_k", "q4_0", "q4_k", "q5_k", "q6_k", "q8_0",
              "f16", "f32", "iq4_xs"):
        if q in name_lower:
            quant = q
            break

    # KV cache estimation
    if layers is not None and layers > 0:
        # Modern LLMs: head_dim ≈ 128, 2 for key+value, float16 = 2 bytes
        head_dim = 128
        kv_per_layer = n_ctx * 2 * head_dim * 2  # bytes
        kv_gb = (layers * kv_per_layer) / (1024 ** 3)
    else:
        # Fallback: KV cache ≈ 20% of model size per 32K context
        kv_gb = model_gb * 0.2 * (n_ctx / 32768)

    total_gb = model_gb + kv_gb

    # Check available memory
    ram_gb = _get_available_ram_gb()
    vram_gb = _get_available_vram_gb()

    fits_ram = total_gb <= ram_gb * 0.9 if ram_gb > 0 else True
    fits_vram = (model_gb + kv_gb * 0.5) <= vram_gb * 0.9 if vram_gb > 0 else False

    return {
        "model_gb": round(model_gb, 2),
        "kv_gb": round(kv_gb, 2),
        "total_gb": round(total_gb, 2),
        "fits_ram": fits_ram,
        "fits_vram": fits_vram,
        "layers": layers,
        "quant": quant,
        "ram_gb": round(ram_gb, 1),
        "vram_gb": round(vram_gb, 1),
    }


def _get_available_ram_gb() -> float:
    """Get available system RAM in GB."""
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass
    try:
        import os
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", c_ulonglong),
                    ("ullAvailPhys", c_ulonglong),
                    ("ullTotalPageFile", c_ulonglong),
                    ("ullAvailPageFile", c_ulonglong),
                    ("ullTotalVirtual", c_ulonglong),
                    ("ullAvailVirtual", c_ulonglong),
                    ("ullAvailExtendedVirtual", c_ulonglong),
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
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def _get_available_vram_gb() -> float:
    """Get available GPU VRAM in GB (best-effort)."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if lines:
                return float(lines[0].strip()) / 1024  # MB to GB
    except Exception:  # noqa: BLE001
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Template auto-detection
# ---------------------------------------------------------------------------

def _template_supports_system(template: str) -> bool:
    """Auto-detect whether a chat template supports system messages.

    This is the Ollama-style smart detection: parse the actual template
    string to determine if system messages are accepted.
    """
    if not template:
        return True  # assume yes if no template

    # Patterns that indicate system messages are NOT supported:
    # 1. Mistral-style: strict alternation + only user/assistant
    if "raise_exception" in template:
        if "Conversation roles must alternate" in template:
            return False
        if "Only user and assistant roles are supported" in template:
            return False

    # 2. Templates that only loop over user/assistant (no system handling)
    # Check if template has explicit system handling
    has_system = (
        "system" in template.lower()
        or "<<SYS>>" in template
        or "<|start_header_id|>system" in template
        or "<|im_start|>system" in template
    )

    # 3. If template only has user/assistant roles in the loop, no system
    if not has_system:
        # Check if the loop only processes user and assistant
        if "message['role'] == 'user'" in template or 'message["role"] == "user"' in template:
            if "message['role'] == 'assistant'" in template or 'message["role"] == "assistant"' in template:
                if "message['role'] == 'system'" not in template and 'message["role"] == "system"' not in template:
                    return False

    return True


# ---------------------------------------------------------------------------
# Family profiles (loaded from model_families.json)
# ---------------------------------------------------------------------------

import json as _json
from pathlib import Path as _Path

def _load_family_profiles() -> List[Dict[str, Any]]:
    """Load model family profiles from model_families.json."""
    json_path = _Path(__file__).parent.parent.parent / "config" / "model_families.json"
    if not json_path.exists():
        logger.warning("model_families.json not found at %s", json_path)
        return _FALLBACK_PROFILES
    try:
        with open(json_path, encoding="utf-8") as f:
            data = _json.load(f)
        families = data.get("families", [])
        # Convert to internal format
        profiles = []
        for fam in families:
            params = fam.get("params", {})
            profiles.append({
                "family": fam["id"],
                "label": fam.get("name", fam["id"]),
                "archs": tuple(fam.get("arch_patterns", [])),
                "names": tuple(fam.get("name_patterns", [])),
                "supports_system_prompt": fam.get("supports_system_prompt", True),
                "temperature": params.get("temperature", 0.7),
                "top_k": params.get("top_k", 40),
                "top_p": params.get("top_p", 0.9),
                "repeat_penalty": params.get("repeat_penalty", 1.05),
                "min_p": params.get("min_p", 0.0),
                "max_tokens": params.get("max_tokens", 4096),
                "context_length": fam.get("context_length", 4096),
                "notes": fam.get("notes", ""),
            })
        logger.info("Loaded %d model families from model_families.json", len(profiles))
        return profiles
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to load model_families.json: %s", e)
        return _FALLBACK_PROFILES


# Fallback profiles when JSON is unavailable
FALLBACK_PROFILES = [
    {
        "family": "liquid-lfm",
        "label": "LiquidAI LFM2",
        "archs": ("lfm2",),
        "names": ("lfm2", "lfm 2"),
        "supports_system_prompt": True,
        "temperature": 0.2, "top_k": 80, "top_p": 0.9,
        "repeat_penalty": 1.05, "min_p": 0.0, "max_tokens": 4096,
    },
    {
        "family": "qwen3",
        "label": "Qwen3",
        "archs": ("qwen3", "qwen3moe"),
        "names": ("qwen3",),
        "supports_system_prompt": True,
        "temperature": 0.6, "top_k": 20, "top_p": 0.95,
        "repeat_penalty": 1.05, "min_p": 0.0, "max_tokens": 4096,
    },
    {
        "family": "llama3",
        "label": "Meta Llama 3.x",
        "archs": ("llama",),
        "names": ("llama-3", "llama3", "meta-llama-3"),
        "supports_system_prompt": True,
        "temperature": 0.6, "top_k": 40, "top_p": 0.9,
        "repeat_penalty": 1.1, "min_p": 0.0, "max_tokens": 4096,
    },
    {
        "family": "mistral",
        "label": "Mistral",
        "archs": (),
        "names": ("mistral",),
        "supports_system_prompt": False,
        "temperature": 0.7, "top_k": 40, "top_p": 0.9,
        "repeat_penalty": 1.1, "min_p": 0.0, "max_tokens": 4096,
    },
    {
        "family": "gpt-oss",
        "label": "OpenAI gpt-oss",
        "archs": ("gpt_oss",),
        "names": ("gpt-oss", "gptoss"),
        "supports_system_prompt": True,
        "temperature": 1.0, "top_k": 40, "top_p": 1.0,
        "repeat_penalty": 1.05, "min_p": 0.0, "max_tokens": 4096,
    },
]

# Load profiles on module import
FAMILY_PROFILES = _load_family_profiles()

# Applied when nothing matches: conservative defaults that behave well on
# most small instruct quants (see the LFM2.5 degeneration incident).
GENERIC_PROFILE = {
    "family": "generic",
    "label": "Generic instruct",
    "archs": (),
    "names": (),
    "supports_system_prompt": True,
    "temperature": 0.2,
    "top_k": 80,
    "top_p": 0.9,
    "repeat_penalty": 1.05,
    "min_p": 0.0,
    "max_tokens": 4096,
}


def detect_family(metadata: Dict[str, str], model_path: str | Path) -> Tuple[Dict[str, Any], str]:
    """Return ``(profile, how_detected)`` for the given model.

    Detection order (Ollama-style):
    1. GGUF architecture string (e.g. "llama", "qwen2", "gemma3")
    2. Filename/metadata name substring match
    3. Fallback to generic profile
    """
    arch = (metadata.get("architecture") or "").lower()
    name = (
        metadata.get("name", "")
        + " "
        + metadata.get("basename", "")
        + " "
        + Path(str(model_path)).name.lower()
    )
    # 1. Try architecture match first (most reliable)
    if arch:
        for prof in FAMILY_PROFILES:
            archs = prof.get("archs", ())
            if any(a in arch for a in archs):
                return prof, f"gguf arch '{arch}'"
    # 2. Try filename/name match
    for prof in FAMILY_PROFILES:
        names = prof.get("names", ())
        if any(n in name for n in names):
            return prof, "filename match"
    # 3. Fallback
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
    # Auto-detect system prompt support from the actual template string
    chat_template = meta.get("chat_template", "")
    supports_system = profile.get("supports_system_prompt", True)
    if chat_template:
        # Override family default with actual template detection
        supports_system = _template_supports_system(chat_template)

    return {
        "family": profile["family"],
        "label": profile.get("label", profile["family"]),
        "detected_via": how,
        "params": params,
        "system_prompt": None,
        "is_embedding_model": is_embedding_model,
        "supports_system_prompt": supports_system,
        "chat_template": chat_template,
        "meta": meta,
    }
