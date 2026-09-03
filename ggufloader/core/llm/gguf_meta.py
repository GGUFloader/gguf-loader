"""Single GGUF header reader (one pass, no tensor access).

Used by the model router AND the chat config / family detection so every
subsystem agrees on architecture, name, chat template, context length,
layer count, and the attention-head geometry needed for GQA-aware KV
cache estimates. Malformed or non-GGUF files yield {} — never raise.

Returned keys:
- every ``general.*`` string, with the ``general.`` prefix stripped
  (``architecture``, ``name``, ``basename``, ...)
- ``tokenizer.chat_template`` as ``chat_template``
- scalar ``<arch>.<suffix>`` values for context_length, block_count,
  embedding_length, attention.head_count, attention.head_count_kv and
  rope.dimension_count, kept under their full prefixed key names.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Dict

_MAGIC = b"GGUF"
_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_T_STRING, _T_ARRAY = 8, 9
# Scalar metadata worth surfacing for memory estimation / GQA math.
_WANT_SUFFIXES = (
    ".context_length",
    ".block_count",
    ".embedding_length",
    ".attention.head_count",
    ".attention.head_count_kv",
    ".rope.dimension_count",
)


def _read_str(f) -> str:
    (n,) = struct.unpack("<Q", f.read(8))
    return f.read(n).decode("utf-8", errors="replace")


def _skip(f, vtype: int) -> Any:
    """Skip (or return) one typed value from the stream."""
    if vtype == _T_STRING:
        return _read_str(f)
    if vtype == _T_ARRAY:
        (etype,) = struct.unpack("<I", f.read(4))
        (count,) = struct.unpack("<Q", f.read(8))
        if etype == _T_STRING:
            for _ in range(count):
                _read_str(f)
            return None
        size = _SIZES.get(etype)
        if size is None:
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


def read(path: str | Path, max_bytes: int = 8 * 1024 * 1024) -> Dict[str, Any]:
    """Read GGUF header metadata without touching tensor data.

    Returns {} for non-GGUF, unsupported-version, or unreadable files.
    """
    out: Dict[str, Any] = {}
    try:
        with open(path, "rb") as f:
            if f.read(4) != _MAGIC:
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
                if key.startswith("general.") and vtype == _T_STRING:
                    out[key[len("general."):]] = _read_str(f)
                elif key == "tokenizer.chat_template" and vtype == _T_STRING:
                    out["chat_template"] = _read_str(f)
                elif vtype in (4, 10) and key.endswith(_WANT_SUFFIXES):
                    out[key] = _skip(f, vtype)
                else:
                    _skip(f, vtype)
    except Exception:  # noqa: BLE001 - malformed file => no metadata
        return {}
    return out
