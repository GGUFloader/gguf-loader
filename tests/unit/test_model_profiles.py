"""Single-model tests: the app is pinned to Gemma 4 12B Instruct (Q4_K_M).

Multi-family detection was removed. The agent-side profile is always the
gemma4 profile, and the router-side detector only ever recognizes gemma4
files (everything else resolves to generic and is rejected at the load gate).
"""

from ggufloader.core.agent.model_profiles import get_profile


def test_gemma4_profile_has_safe_defaults():
    p = get_profile("gemma-4-12b-it-Q4_K_M.gguf", n_ctx_train=8192)
    assert p.max_tokens <= 4096
    assert p.max_steps >= 16
    assert p.temperature <= 0.2
    assert p.n_ctx_target == 8192
    assert p.n_batch >= 256
    assert p.flash_attn is True


def test_any_model_path_gets_pinned_gemma4_profile():
    """Agent-side profiles are no longer detected per file - one target."""
    for name in ("gemma-4-12b-it-Q4_K_M.gguf", "mystery-99b-F16.gguf"):
        p = get_profile(name)
        assert p.max_tokens == 4096
        assert p.max_steps == 20
        assert p.temperature == 0.1


def test_ctx_clamped_by_trained_context():
    p = get_profile("gemma-4-12b-it-Q4_K_M.gguf", n_ctx_train=4096)
    assert p.n_ctx_target == 4096  # clamped to the file's trained context
    p2 = get_profile("gemma-4-12b-it-Q4_K_M.gguf")  # no ctx info -> target
    assert p2.n_ctx_target == 8192


# ---------------------------------------------------------------------------
# Router-side detection: gemma4 is the ONLY family that exists
# ---------------------------------------------------------------------------

def test_gemma4_arch_resolves_to_pinned_family():
    from ggufloader.core.llm.model_profiles import detect_family
    prof, via = detect_family(
        {"architecture": "gemma4", "name": "gemma-4-12b-it"},
        "gemma-4-12b-it-Q4_K_M.gguf")
    assert prof["family"] == "gemma4", prof["family"]
    assert "gemma4" in via or "arch" in via, via


def test_gemma4_name_match_without_arch():
    from ggufloader.core.llm.model_profiles import detect_family
    prof, via = detect_family({}, "gemma-4-12b-it-Q4_K_M.gguf")
    assert prof["family"] == "gemma4", prof["family"]


def test_non_gemma_models_fall_to_generic():
    """llama / gemma3 / qwen files no longer resolve to their own tuning."""
    from ggufloader.core.llm.model_profiles import detect_family
    cases = [
        {"architecture": "llama", "name": "Meta Llama 3 8B Instruct"},
        {"architecture": "gemma3", "name": "gemma-3-8b-it"},
        {"architecture": "qwen2", "name": "Qwen2.5-7B-Instruct"},
    ]
    for meta in cases:
        prof, via = detect_family(meta, "model.gguf")
        assert prof["family"] == "generic", (meta, prof["family"])
        assert via  # non-empty explanation


def test_unknown_file_never_crashes_returns_generic():
    from ggufloader.core.llm.model_profiles import detect_family
    prof, via = detect_family({}, "mystery-model-9b-q8_0.gguf")
    assert prof["family"] == "generic"
    assert via  # non-empty explanation
