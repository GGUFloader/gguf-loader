"""Single-model (Gemma 4 12B Q4_K_M) configuration.

The app is pinned to ONE model: Google Gemma 4 12B Instruct in Q4_K_M.
Multi-family auto-detection was removed; the only family profile is
``gemma4`` (see ``ggufloader/config/model_families.json``). GGUF metadata
is still read (pure Python, header only) for the file's real context
length, layer count and quant, so context/offload planning stays accurate
for the pinned target. Files that are not Gemma 4 are detected as
``generic`` and rejected at the model load gate.

Sampling follows the official Gemma 4 model card (1.0 / 0.95 / 64); the
agent role still caps temperature/top_k for reliable structured output.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# GGUF metadata reading is centralized in core/llm/gguf_meta.py (single
# reader shared with the router). See read_gguf_general_metadata below.

def read_gguf_general_metadata(
    path: str | Path, max_bytes: int = 8 * 1024 * 1024
) -> Dict[str, Any]:
    """Return model metadata from the GGUF header (no tensor access).

    Compatibility shim over the single shared reader in
    ``ggufloader.core.llm.gguf_meta`` (Task 1: one reader everywhere).
    Collects:
    - Every ``general.*`` string (architecture, name, etc.)
    - ``tokenizer.chat_template`` for template-based system prompt detection
    - Scalar ``<arch>.context_length`` and ``<arch>.block_count`` entries

    Raises nothing; returns {} for non-GGUF or unreadable files.
    """
    from ggufloader.core.llm.gguf_meta import read as _gguf_meta_read
    return _gguf_meta_read(path, max_bytes)


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
        return FALLBACK_PROFILES
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
                "version_patterns": tuple(fam.get("version_patterns", [])),
                "supports_system_prompt": fam.get("supports_system_prompt", True),
                "system_prompt": fam.get("system_prompt", ""),
                "task_prompts": fam.get("task_prompts", {}),
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
        return FALLBACK_PROFILES


# Fallback profile when the JSON is unavailable: the single pinned
# Gemma 4 12B Instruct target (mirrors ggufloader/config/model_families.json).
FALLBACK_PROFILES = [
    {
        "family": "gemma4",
        "label": "Google Gemma 4 12B Instruct",
        "archs": ("gemma4",),
        "names": ("gemma-4", "gemma4"),
        "version_patterns": (),
        "supports_system_prompt": True,
        "system_prompt": (
            "You are a helpful file assistant running on Gemma 4 12B. You read "
            "files, search the workspace, run commands, and help users "
            "understand and modify their project.\n\n"
            "Respond with ONLY a JSON object (no markdown):\n"
            '{"reasoning": "what you plan to do", "estimated_steps": 3, '
            '"tool_calls": [{"tool": "tool_name", "parameters": {}}], "answer": ""}\n\n'
            "When answering:\n"
            '{"reasoning": "summary", "estimated_steps": 0, "tool_calls": [], '
            '"answer": "your answer"}\n\n'
            "Rules: tool_calls and answer are mutually exclusive. Think step by "
            "step, keep reasoning concise, and always finish with either the "
            "tool call you need or the final answer."
        ),
        "temperature": 1.0, "top_k": 64, "top_p": 0.95,
        "repeat_penalty": 1.0, "min_p": 0.0, "max_tokens": 8192,
        "context_length": 131072,
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

    Single-model app: only the ``gemma4`` family exists. Gemma 4 files
    (GGUF arch ``gemma4`` or a gemma-4/gemma4 name) resolve to the pinned
    profile; everything else falls through to the conservative generic
    profile and is rejected at the model load gate.
    """
    arch = (metadata.get("architecture") or "").lower()
    name = (
        str(metadata.get("name") or "").lower()
        + " "
        + str(metadata.get("basename") or "").lower()
        + " "
        + Path(str(model_path)).name.lower()
    )

    # 0. Version patterns win: llama-2-7b must NOT resolve to the llama3
    # profile just because both expose arch "llama" (longest version hit wins
    # so "llama-3.1" isn't swallowed by an earlier "llama-3" family).
    # Version patterns only apply when the family's arch set is compatible
    # (or the file has no arch at all) - "gemma-2-9b" must never match
    # llama2's "-2-" version marker.
    best_ver = None
    best_len = -1
    for prof in FAMILY_PROFILES:
        archs = prof.get("archs", ())
        if arch and archs and not any(a in arch for a in archs):
            continue  # wrong arch family - never version-match across archs
        for vp in prof.get("version_patterns", ()):
            if vp and vp.lower() in name and len(vp) > best_len:
                best_len, best_ver = len(vp), prof
    if best_ver is not None:
        return best_ver, "version match"

    # 1. Architecture match, longest arch pattern first - keeps e.g. a
    # "gemma3" arch file from matching the "gemma2" arch family just
    # because "gemma2" is a substring of the family list order. Ties (two
    # families sharing one arch, e.g. llama2/llama3/codellama on "llama")
    # are broken by the family name appearing in the file name.
    if arch:
        best_arch = None
        best_arch_len = -1
        best_arch_name_hit = False
        for prof in FAMILY_PROFILES:
            for a in prof.get("archs", ()):
                if not (a and a in arch):
                    continue
                name_hit = any(n and n.lower() in name for n in prof.get("names", ()))
                if len(a) > best_arch_len or (
                        len(a) == best_arch_len and name_hit and not best_arch_name_hit):
                    best_arch_len, best_arch, best_arch_name_hit = len(a), prof, name_hit
        if best_arch is not None:
            return best_arch, f"gguf arch '{arch}'"

    # 2. Try filename/name match
    for prof in FAMILY_PROFILES:
        names = prof.get("names", ())
        if any(n and n.lower() in name for n in names):
            return prof, "filename match"
    # 3. Fallback
    return GENERIC_PROFILE, "generic-fallback"


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
        "system_prompt": profile.get("system_prompt", ""),
        "is_embedding_model": is_embedding_model,
        "supports_system_prompt": supports_system,
        "chat_template": chat_template,
        "meta": meta,
    }
