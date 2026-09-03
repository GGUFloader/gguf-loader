"""Tests for the rich model router (core/router.py)."""

import struct

import pytest
from pathlib import Path

from ggufloader.core.router import (
    LoadStrategy,
    ModelProfile,
    ModelRole,
    ModelRouter,
    QuantTier,
    SizeTier,
    SystemProfile,
    _estimate_memory_detailed,
    _is_embedding_model,
    _is_thinking_model,
    _param_estimate_from_filename,
    _size_tier_from_gb,
)


# ---------------------------------------------------------------------------
# GGUF test fixture
# ---------------------------------------------------------------------------

def _kv_str(key: str, val: str) -> bytes:
    k = key.encode()
    v = val.encode()
    return (
        struct.pack("<Q", len(k)) + k
        + struct.pack("<I", 8)
        + struct.pack("<Q", len(v)) + v
    )


def _kv_u32(key: str, val: int) -> bytes:
    k = key.encode()
    return (
        struct.pack("<Q", len(k)) + k
        + struct.pack("<I", 4)
        + struct.pack("<I", val)
    )


def _make_gguf(kvs: bytes, kv_count: int = 2) -> bytes:
    return (
        b"GGUF"
        + struct.pack("<I", 3)
        + struct.pack("<Q", 1)        # tensor count
        + struct.pack("<Q", kv_count)  # kv count
        + kvs
    )


def _create_model_file(tmp_path: Path, name: str, kvs: bytes, kv_count: int = 2,
                       extra_bytes: int = 64) -> Path:
    p = tmp_path / name
    p.write_bytes(_make_gguf(kvs, kv_count) + b"\x00" * extra_bytes)
    return p


# ---------------------------------------------------------------------------
# System profile
# ---------------------------------------------------------------------------

def test_system_profile_detect_does_not_crash():
    """SystemProfile.detect() should always return a valid object."""
    sys = SystemProfile.detect()
    assert isinstance(sys.ram_gb, float)
    assert isinstance(sys.cpu_cores, int)
    assert sys.cpu_cores > 0


# ---------------------------------------------------------------------------
# Size tier
# ---------------------------------------------------------------------------

def test_size_tier_boundaries():
    assert _size_tier_from_gb(0.5) == SizeTier.TINY
    assert _size_tier_from_gb(1.5) == SizeTier.SMALL
    assert _size_tier_from_gb(4.0) == SizeTier.MEDIUM
    assert _size_tier_from_gb(8.0) == SizeTier.LARGE
    assert _size_tier_from_gb(15.0) == SizeTier.XLARGE
    assert _size_tier_from_gb(35.0) == SizeTier.XXLARGE
    assert _size_tier_from_gb(50.0) == SizeTier.MEGA


# ---------------------------------------------------------------------------
# Param estimate from filename
# ---------------------------------------------------------------------------

def test_param_estimate_from_filename():
    assert _param_estimate_from_filename("Qwen3-8B-Instruct-Q4_K_M.gguf") == "8B"
    assert _param_estimate_from_filename("Mistral-7B-v0.1.gguf") == "7B"
    assert _param_estimate_from_filename("DeepSeek-R1-Distill-Qwen-14B.gguf") == "14B"
    assert _param_estimate_from_filename("LFM2.5-8B-Q4_K_M.gguf") == "8B"
    assert _param_estimate_from_filename("model.gguf") == ""


# ---------------------------------------------------------------------------
# Capability detection
# ---------------------------------------------------------------------------

def test_is_embedding_model():
    assert _is_embedding_model("nomic-bert", "nomic-embed", "nomic") is True
    assert _is_embedding_model("llama", "Llama-3-8B", "llama3") is False
    assert _is_embedding_model("", "snowflake-arctic-embed", "") is True


def test_is_thinking_model():
    assert _is_thinking_model("qwen3", "QwQ-32B", "qwq-32b.gguf") is True
    assert _is_thinking_model("llama", "Llama-3-8B", "llama3-8b.gguf") is False
    assert _is_thinking_model("", "", "DeepSeek-R1-Distill-Qwen-7B.gguf") is True


# ---------------------------------------------------------------------------
# Memory estimation
# ---------------------------------------------------------------------------

def test_estimate_memory_detailed():
    model_gb, kv_gb, bpl = _estimate_memory_detailed(4.0, 32, 32768)
    assert model_gb == 4.0
    # 32k ctx, 32 layers, 8 GQA kv heads x dim 128 x fp16 = 4.0 GiB
    assert kv_gb == pytest.approx(4.0, abs=0.05)
    assert bpl == pytest.approx(4.0 / 32)


def test_estimate_memory_no_layers():
    model_gb, kv_gb, bpl = _estimate_memory_detailed(4.0, 0, 32768)
    assert model_gb == 4.0
    assert kv_gb > 0  # fallback estimation
    assert bpl == 0.0


# ---------------------------------------------------------------------------
# Router inspect
# ---------------------------------------------------------------------------

def test_router_inspect_llama_model(tmp_path):
    kvs = (
        _kv_str("general.architecture", "llama")
        + _kv_str("general.name", "Llama-3-8B-Instruct")
        + _kv_u32("llama.context_length", 8192)
        + _kv_u32("llama.block_count", 32)
    )
    p = _create_model_file(tmp_path, "Llama-3-8B-Q4_K_M.gguf", kvs, kv_count=4)
    # Pad file to ~4 GB to simulate real model size
    # (We can't actually create a 4 GB file in tests, so we test metadata only)
    router = ModelRouter()
    profile = router.inspect(str(p))

    assert profile.architecture == "llama"
    assert profile.family == "llama3"
    assert profile.trained_context == 8192
    assert profile.total_layers == 32
    assert profile.is_embedding_model is False
    assert profile.is_thinking_model is False
    assert profile.supports_system_prompt is True


def test_router_inspect_embedding_model(tmp_path):
    kvs = (
        _kv_str("general.architecture", "nomic-bert")
        + _kv_str("general.name", "nomic-embed-text-v1.5")
    )
    p = _create_model_file(tmp_path, "nomic-embed-text-v1.5.gguf", kvs)
    router = ModelRouter()
    profile = router.inspect(str(p))

    assert profile.is_embedding_model is True
    assert profile.architecture == "nomic-bert"


def test_router_inspect_thinking_model(tmp_path):
    kvs = (
        _kv_str("general.architecture", "qwen3")
        + _kv_str("general.name", "QwQ-32B")
    )
    p = _create_model_file(tmp_path, "QwQ-32B-Q4_K_M.gguf", kvs)
    router = ModelRouter()
    profile = router.inspect(str(p))

    assert profile.is_thinking_model is True


def test_router_inspect_file_not_found():
    router = ModelRouter()
    try:
        router.inspect("/nonexistent/model.gguf")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Router plan
# ---------------------------------------------------------------------------

def test_plan_cpu_only_system():
    sys = SystemProfile(ram_gb=16.0, vram_gb=0.0, has_gpu_support=False)
    router = ModelRouter(system=sys)
    profile = ModelProfile(
        path="/test.gguf", file_size_gb=4.0, total_layers=32,
        model_memory_gb=4.0, kv_memory_gb=1.0, total_memory_gb=5.0,
    )
    strategy = router.plan(profile)

    assert strategy.use_gpu is False
    assert strategy.n_gpu_layers == 0
    assert strategy.fits_ram is True
    assert "CPU" in strategy.reasoning or "No GPU" in strategy.reasoning


def test_plan_gpu_full_offload():
    sys = SystemProfile(ram_gb=32.0, vram_gb=24.0, has_gpu_support=True)
    router = ModelRouter(system=sys)
    profile = ModelProfile(
        path="/test.gguf", file_size_gb=4.0, total_layers=32,
        model_memory_gb=4.0, kv_memory_gb=1.0, total_memory_gb=5.0,
    )
    strategy = router.plan(profile)

    assert strategy.use_gpu is True
    assert strategy.n_gpu_layers == -1  # all layers
    assert "full GPU" in strategy.reasoning.lower() or "fits" in strategy.reasoning.lower()


def test_plan_gpu_partial_offload():
    # 8 GB VRAM, 85% = 6.8 GB. Model is 7 GB → exceeds 85% but under 120%
    sys = SystemProfile(ram_gb=32.0, vram_gb=8.0, has_gpu_support=True)
    router = ModelRouter(system=sys)
    profile = ModelProfile(
        path="/test.gguf", file_size_gb=7.0, total_layers=32,
        model_memory_gb=7.0, kv_memory_gb=2.0, total_memory_gb=9.0,
    )
    strategy = router.plan(profile)

    assert strategy.use_gpu is True
    assert 0 < strategy.n_gpu_layers <= 32  # partial offload


def test_plan_gpu_too_large_for_vram():
    sys = SystemProfile(ram_gb=64.0, vram_gb=8.0, has_gpu_support=True)
    router = ModelRouter(system=sys)
    profile = ModelProfile(
        path="/test.gguf", file_size_gb=20.0, total_layers=80,
        model_memory_gb=20.0, kv_memory_gb=4.0, total_memory_gb=24.0,
    )
    strategy = router.plan(profile)

    assert strategy.use_gpu is False
    assert strategy.fits_ram is True


def test_plan_embedding_model_prefers_cpu():
    sys = SystemProfile(ram_gb=16.0, vram_gb=24.0, has_gpu_support=True)
    router = ModelRouter(system=sys)
    profile = ModelProfile(
        path="/test.gguf", file_size_gb=0.3, is_embedding_model=True,
        model_memory_gb=0.3, total_memory_gb=0.3,
    )
    strategy = router.plan(profile)

    assert strategy.use_gpu is False
    assert "Embedding" in strategy.reasoning


# ---------------------------------------------------------------------------
# Router route (role-based)
# ---------------------------------------------------------------------------

def test_route_chat():
    router = ModelRouter()
    profile = ModelProfile(family_params={"temperature": 0.7, "top_k": 40})
    config = router.route(profile, ModelRole.CHAT)

    assert config.role == ModelRole.CHAT
    assert config.temperature == 0.7
    assert config.top_k == 40


def test_route_agent_overrides_temperature():
    router = ModelRouter()
    profile = ModelProfile(family_params={"temperature": 0.8})
    config = router.route(profile, ModelRole.AGENT)

    assert config.temperature <= 0.3  # agent caps temp
    assert config.repeat_penalty >= 1.1


def test_route_code_allows_higher_temperature():
    router = ModelRouter()
    profile = ModelProfile(family_params={"temperature": 0.2})
    config = router.route(profile, ModelRole.CODE)

    assert config.temperature >= 0.4  # code mode raises temp


def test_route_reasoning_thinking_budget():
    router = ModelRouter()
    profile = ModelProfile(is_thinking_model=True)
    config = router.route(profile, ModelRole.CHAT)

    assert config.max_tokens >= 16384  # thinking models get bigger budget


def test_route_embed_has_zero_temperature():
    router = ModelRouter()
    profile = ModelProfile()
    config = router.route(profile, ModelRole.EMBED)

    assert config.temperature == 0.0
    assert config.max_tokens == 0


def test_route_capped_to_trained_context():
    router = ModelRouter()
    profile = ModelProfile(trained_context=2048)
    config = router.route(profile, ModelRole.CHAT)

    assert config.max_tokens <= 2048 - 256


# ---------------------------------------------------------------------------
# Suggest role
# ---------------------------------------------------------------------------

def test_suggest_role_embedding():
    router = ModelRouter()
    profile = ModelProfile(is_embedding_model=True)
    assert router.suggest_role(profile) == ModelRole.EMBED


def test_suggest_role_thinking():
    router = ModelRouter()
    profile = ModelProfile(is_thinking_model=True)
    assert router.suggest_role(profile) == ModelRole.REASONING


def test_suggest_role_vision():
    router = ModelRouter()
    profile = ModelProfile(supports_vision=True)
    assert router.suggest_role(profile) == ModelRole.MULTIMODAL


def test_suggest_role_default_chat():
    router = ModelRouter()
    profile = ModelProfile()
    assert router.suggest_role(profile) == ModelRole.CHAT


# ---------------------------------------------------------------------------
# Can serve role
# ---------------------------------------------------------------------------

def test_can_serve_role():
    router = ModelRouter()
    embed_profile = ModelProfile(is_embedding_model=True)
    chat_profile = ModelProfile()

    assert router.can_serve_role(embed_profile, ModelRole.EMBED) is True
    assert router.can_serve_role(embed_profile, ModelRole.CHAT) is False
    assert router.can_serve_role(chat_profile, ModelRole.CHAT) is True
    assert router.can_serve_role(chat_profile, ModelRole.AGENT) is True


# ---------------------------------------------------------------------------
# Quick profile
# ---------------------------------------------------------------------------

def test_quick_profile(tmp_path):
    kvs = (
        _kv_str("general.architecture", "llama")
        + _kv_str("general.name", "Llama-3-8B")
    )
    p = _create_model_file(tmp_path, "Llama-3-8B-Q4_K_M.gguf", kvs)
    router = ModelRouter()
    qp = router.quick_profile(str(p))

    assert qp["architecture"] == "llama"
    assert qp["family"] == "llama3"
    assert qp["is_embedding"] is False
    assert "filename" in qp


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_router_handles_minimal_gguf(tmp_path):
    """GGUF with only architecture set, no name/layers/context."""
    kvs = _kv_str("general.architecture", "qwen3")
    p = _create_model_file(tmp_path, "qwen3-custom.gguf", kvs)
    router = ModelRouter()
    profile = router.inspect(str(p))

    assert profile.architecture == "qwen3"
    assert profile.family == "qwen3"
    assert profile.total_layers == 0  # not set
    assert profile.trained_context == 0


def test_router_handles_non_gguf_file(tmp_path):
    """Non-GGUF file should still produce a profile (with empty metadata)."""
    p = tmp_path / "not-a-model.bin"
    p.write_bytes(b"NOTGGUF" * 10)
    router = ModelRouter()
    profile = router.inspect(str(p))

    assert profile.architecture == ""
    assert profile.family == "generic"  # fallback


def test_all_roles_produce_valid_config():
    """Every role should produce a valid RoleConfig."""
    router = ModelRouter()
    profile = ModelProfile()
    for role in ModelRole:
        config = router.route(profile, role)
        assert config.role == role
        assert isinstance(config.temperature, float)
        assert isinstance(config.top_k, int)
        assert isinstance(config.max_tokens, int)


# ---------------------------------------------------------------------------
# Task 1: single shared GGUF reader with attention-head fields
# ---------------------------------------------------------------------------

def test_gguf_meta_reads_heads(tmp_path):
    """The shared reader (gguf_meta) exposes GQA fields: head counts, dims."""
    from ggufloader.core.llm.gguf_meta import read as meta_read
    kvs = (
        _kv_str("general.architecture", "gemma3")
        + _kv_str("general.name", "gemma-3-8b-it")
        + _kv_u32("gemma3.context_length", 8192)
        + _kv_u32("gemma3.block_count", 32)
        + _kv_u32("gemma3.embedding_length", 3072)
        + _kv_u32("gemma3.attention.head_count", 16)
        + _kv_u32("gemma3.attention.head_count_kv", 8)
    )
    p = tmp_path / "gemma-3-8b-it-Q4_K_M.gguf"
    p.write_bytes(_make_gguf(kvs, kv_count=7) + b"\x00" * 64)
    meta = meta_read(str(p))
    assert meta["architecture"] == "gemma3"
    assert meta["gemma3.block_count"] == 32
    assert meta["gemma3.attention.head_count_kv"] == 8


def test_gguf_meta_shared_across_readers(tmp_path):
    """router and model_profiles must agree byte-for-byte with gguf_meta."""
    from ggufloader.core.llm.gguf_meta import read as meta_read
    from ggufloader.core.router import _read_gguf_metadata
    from ggufloader.core.llm.model_profiles import read_gguf_general_metadata
    kvs = (
        _kv_str("general.architecture", "llama")
        + _kv_str("general.name", "Llama-3-8B-Instruct")
        + _kv_u32("llama.context_length", 8192)
        + _kv_u32("llama.block_count", 32)
        + _kv_u32("llama.attention.head_count", 32)
        + _kv_u32("llama.attention.head_count_kv", 8)
    )
    p = _create_model_file(tmp_path, "llama-3-8b.gguf", kvs, kv_count=6)
    shared = meta_read(p)
    assert _read_gguf_metadata(p) == shared
    assert read_gguf_general_metadata(p) == shared
    assert shared["architecture"] == "llama"
    assert shared["llama.attention.head_count_kv"] == 8
