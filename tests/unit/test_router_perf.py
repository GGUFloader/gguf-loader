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


# ---------------------------------------------------------------------------
# Task 3: fit-aware plan() + reserve-aware partial offload
# ---------------------------------------------------------------------------

def _router_8gb_32gb():
    return ModelRouter(system=SystemProfile(
        ram_gb=32.0, vram_gb=8.0, has_gpu_support=True))


def test_plan_caps_ctx_by_vram_not_trained():
    r = _router_8gb_32gb()
    prof = ModelProfile(filename="huge-70b-Q4.gguf", file_size_gb=40.0,
                        total_layers=80, trained_context=128000, model_memory_gb=40.0)
    s = r.plan(prof)
    assert s.n_ctx <= 8192  # must NOT return min(128000, 32768)=32768 on 8GB
    assert s.use_gpu is False


def test_plan_partial_reserves_kv():
    r = _router_8gb_32gb()
    prof = ModelProfile(filename="qwen-14b-Q4.gguf", file_size_gb=8.0,
                        total_layers=40, trained_context=32768, model_memory_gb=8.0)
    s = r.plan(prof)
    assert 0 < s.n_gpu_layers < 40  # partial, not full, not CPU
    assert "Partial" in s.reasoning


def test_plan_full_offload_checks_kv_too():
    # 4.9 GB model fits VRAM alone but model+KV at 32k ctx does not.
    r = _router_8gb_32gb()
    prof = ModelProfile(filename="gemma-8-q4.gguf", file_size_gb=4.9,
                        total_layers=32, trained_context=32768, model_memory_gb=4.9,
                        kv_heads=8, head_dim=128)
    s = r.plan(prof)
    # KV at 32k ~= 4 GiB -> total ~9 GiB > 6.8 usable; must drop ctx.
    assert s.n_ctx <= 16384


def test_plan_reasoning_reports_partial_layers():
    r = _router_8gb_32gb()
    prof = ModelProfile(filename="qwen-14b-Q4.gguf", file_size_gb=8.0,
                        total_layers=40, trained_context=32768, model_memory_gb=8.0)
    s = r.plan(prof)
    assert s.bytes_per_layer == pytest.approx(8.0 / 40, abs=0.001)
    assert "of 40" in s.reasoning


def test_plan_with_overrides_recomputes_fits():
    r = _router_8gb_32gb()
    prof = ModelProfile(filename="gemma-3-8b-it-Q4_K_M.gguf", file_size_gb=5.0,
                        total_layers=32, trained_context=8192, model_memory_gb=5.0,
                        kv_heads=8, head_dim=128)
    auto = r.plan(prof)
    assert auto.fits_vram  # 5 GB model + 1 GB KV at 8k ctx fits 6.8 GB usable
    forced = r.plan_with_overrides(prof, n_ctx=32768)
    # Same model forced to 32k ctx must NOT still claim fits_vram.
    assert forced.n_ctx == 32768
    assert forced.fits_vram is False


# ---------------------------------------------------------------------------
# Task 14: golden verification matrix (Gemma-8-Q4 on 8GB/32GB + edge cases)
# ---------------------------------------------------------------------------

def test_golden_gemma8_8gb_vram():
    """The reference rig's canonical plan: full GPU offload at 8k context."""
    r = ModelRouter(system=SystemProfile(
        ram_gb=32.0, vram_gb=8.0, gpu_name="8GB", gpu_backend="cuda",
        cpu_cores=12, has_gpu_support=True))
    p = ModelProfile(filename="gemma-3-8b-it-Q4_K_M.gguf", file_size_gb=5.0,
                     total_layers=32, trained_context=8192, model_memory_gb=5.0,
                     kv_heads=8, head_dim=128)
    s = r.plan(p)
    assert (s.n_ctx, s.n_gpu_layers, s.use_gpu) == (8192, -1, True)
    assert s.batch_size == 512 and s.fits_vram and s.fits_ram


def test_golden_14b_partial_and_70b_cpu():
    """14B partial-offloads on 8GB; a 40GB 70B stays on CPU at low ctx."""
    r = ModelRouter(system=SystemProfile(
        ram_gb=32.0, vram_gb=8.0, has_gpu_support=True))
    s1 = r.plan(ModelProfile(filename="qwen-14b-Q4.gguf", file_size_gb=8.0,
                             total_layers=40, trained_context=32768,
                             model_memory_gb=8.0, kv_heads=8, head_dim=128))
    assert 0 < s1.n_gpu_layers < 40
    s2 = r.plan(ModelProfile(filename="huge-70b-Q4.gguf", file_size_gb=40.0,
                             total_layers=80, trained_context=8192,
                             model_memory_gb=40.0))
    assert s2.use_gpu is False and s2.n_ctx <= 8192
