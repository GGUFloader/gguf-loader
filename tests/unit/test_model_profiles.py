"""Model-profile router: GGUF metadata parsing + family detection."""

import struct

from ggufloader.core.llm.model_profiles import (
    GENERIC_PROFILE,
    detect_family,
    read_gguf_general_metadata,
    resolve_chat_config,
)


def _kv_str(key: str, val: str) -> bytes:
    k = key.encode()
    v = val.encode()
    return struct.pack("<Q", len(k)) + k + struct.pack("<I", 8) + \
        struct.pack("<Q", len(v)) + v


def _kv_u32(key: str, val: int) -> bytes:
    k = key.encode()
    return struct.pack("<Q", len(k)) + k + struct.pack("<I", 4) + struct.pack("<I", val)


def _kv_str_array(key: str, vals) -> bytes:
    k = key.encode()
    body = struct.pack("<I", 9) + struct.pack("<I", 8) + struct.pack("<Q", len(vals))
    for v in vals:
        b = v.encode()
        body += struct.pack("<Q", len(b)) + b
    return struct.pack("<Q", len(k)) + k + body


def make_gguf(kvs: bytes, kv_count: int = 3) -> bytes:
    return (b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 1)
            + struct.pack("<Q", kv_count) + kvs)


def test_parser_reads_general_and_skips_rest(tmp_path):
    blob = make_gguf(
        _kv_str("general.architecture", "lfm2")
        + _kv_u32("some.uint", 7)
        + _kv_str_array("tokenizer.ggml.tokens", ["a", "b", "c"])
        + _kv_str("general.name", "LFM2.5-8B-Instruct"),
        kv_count=4,
    )
    p = tmp_path / "m.gguf"
    p.write_bytes(blob + b"\x00" * 64)
    meta = read_gguf_general_metadata(p)
    assert meta == {"architecture": "lfm2", "name": "LFM2.5-8B-Instruct"}


def test_parser_rejects_non_gguf(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"NOPE" * 10)
    assert read_gguf_general_metadata(p) == {}


def test_detect_by_arch():
    prof, how = detect_family({"architecture": "lfm2"}, "whatever.gguf")
    assert prof["family"] == "liquid-lfm"
    assert "arch" in how
    assert prof["temperature"] == 0.2 and prof["top_k"] == 80


def test_detect_by_filename_fallback():
    prof, how = detect_family({}, r"F:\m\DeepSeek-R1-Distill-Qwen-7B.gguf")
    assert prof["family"] == "deepseek-r1"
    assert "filename" in how
    # llama arch string alone maps to llama3 profile via archs tuple
    prof2, _ = detect_family({"architecture": "llama"}, "custom.gguf")
    assert prof2["family"] == "llama3"


def test_generic_fallback_is_conservative():
    prof, how = detect_family({}, "unknown-model-xyz.gguf")
    assert prof["family"] == GENERIC_PROFILE["family"]
    assert prof["temperature"] == 0.2  # degeneracy-safe default
    assert how == "no match"


def test_resolve_config_user_overrides_family(tmp_path, monkeypatch):
    from ggufloader.core.llm import model_params
    f = tmp_path / "model_params.json"
    f.write_text('{"lfm": {"temperature": 0.35}}', encoding="utf-8")
    monkeypatch.setattr(model_params, "_candidate_files", lambda: [f])
    cfg = resolve_chat_config(r"F:\m\LFM2.5-8B-Q4_K_M.gguf")
    assert cfg["family"] == "liquid-lfm"
    assert cfg["params"]["temperature"] == 0.35      # user wins
    assert cfg["params"]["top_k"] == 80              # family fills the rest
