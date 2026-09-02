from ggufloader.core.agent.model_profiles import get_profile, AGENT_PROFILE_REGISTRY


def test_gemma4_profile_has_safe_defaults():
    p = get_profile("gemma-4-12b-it-Q4_K_M.gguf", n_ctx_train=8192)
    assert p.max_tokens <= 4096
    assert p.max_steps >= 16
    assert p.temperature <= 0.2
    assert p.n_ctx_target == 8192
    assert p.n_batch >= 256
    assert p.flash_attn is True


def test_default_profile_exists():
    assert "default" in AGENT_PROFILE_REGISTRY
    p = AGENT_PROFILE_REGISTRY["default"]
    assert p.max_tokens == 4096
    assert p.max_steps == 16


def test_unknown_model_uses_default():
    p = get_profile("mystery-99b-F16.gguf", n_ctx_train=32768)
    default = AGENT_PROFILE_REGISTRY["default"]
    assert p.max_tokens == default.max_tokens
    assert p.max_steps == default.max_steps
    assert p.n_ctx_target == min(8192, 32768)