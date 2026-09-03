"""Router max-performance tests: GQA KV math, VRAM/RAM fits, golden plans.

All fixtures are synthetic GGUF profiles — no GPU or model load required.
"""

import pytest

from ggufloader.core.router import (
    ModelProfile,
    ModelRouter,
    SystemProfile,
    _estimate_memory_detailed,
)


# ---------------------------------------------------------------------------
# Task 2: GQA-accurate memory model
# ---------------------------------------------------------------------------

def test_gqa_kv_math():
    # 32 layers, 8 kv heads, dim 128, ctx 8192:
    # kv = 8192*2*32*8*128*2 bytes = 1.0 GiB
    model_gb, kv_gb, bpl = _estimate_memory_detailed(
        5.0, 32, 8192, kv_heads=8, head_dim=128)
    assert kv_gb == pytest.approx(1.0, abs=0.05)
    assert bpl == pytest.approx(5.0 / 32, abs=0.01)


def test_gqa_kv_math_kv_heads_matter():
    # GQA: 4 kv heads vs 32 kv heads must NOT give the same KV estimate.
    _, kv_4, _ = _estimate_memory_detailed(5.0, 32, 8192, kv_heads=4, head_dim=128)
    _, kv_32, _ = _estimate_memory_detailed(5.0, 32, 8192, kv_heads=32, head_dim=128)
    assert kv_32 == pytest.approx(kv_4 * 8, rel=0.01)


def test_estimate_memory_no_layers_fallback():
    model_gb, kv_gb, bpl = _estimate_memory_detailed(5.0, 0, 8192)
    assert model_gb == pytest.approx(5.0)
    assert kv_gb > 0
    assert bpl == 0.0


# ---------------------------------------------------------------------------
# Canonical defaults single source
# ---------------------------------------------------------------------------

def test_defaults_module_exists_and_canonical():
    from ggufloader.core import defaults
    assert defaults.DEFAULT_CTX == 8192
    assert 32768 in defaults.CTX_OPTIONS
    assert defaults.VRAM_HEADROOM == 0.85
    assert defaults.RAM_HEADROOM == 0.8
    assert defaults.CUDA_RESERVE_GB == 1.0
    assert "<end_of_turn>" in defaults.STOP_TOKENS_UNIFIED
    # The bare lowercase "user:" trap must not live in the canonical stop set.
    assert "user:" not in defaults.STOP_TOKENS_UNIFIED
