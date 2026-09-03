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

# ---------------------------------------------------------------------------
# Robust detection (Task 11): version-aware family detection for arbitrary
# user files. Detection order must be: version patterns > name > bare arch,
# with the longest arch substring winning.
# ---------------------------------------------------------------------------

def test_version_patterns_distinguish_llama2_from_llama3():
    from ggufloader.core.llm.model_profiles import detect_family
    # Both share GGUF arch "llama" - the version in the name decides.
    prof2, via2 = detect_family(
        {"architecture": "llama", "name": "Meta Llama 2 7B Chat"},
        "Meta-Llama-2-7B-Chat.Q4_K_M.gguf")
    assert prof2["family"] == "llama2", prof2["family"]
    assert "version" in via2 or "name" in via2, via2

    prof3, via3 = detect_family(
        {"architecture": "llama", "name": "Meta Llama 3 8B Instruct"},
        "Meta-Llama-3-8B-Instruct.Q4_K_M.gguf")
    assert prof3["family"] == "llama3", prof3["family"]


def test_name_beats_ambiguous_arch():
    from ggufloader.core.llm.model_profiles import detect_family
    # Codellama reports arch "llama" (shared with llama2/3); its name must win.
    prof, via = detect_family(
        {"architecture": "llama", "name": "Code Llama 7B"},
        "codellama-7b-instruct.Q4_K_M.gguf")
    assert prof["family"] == "codellama", prof["family"]


def test_gemma_3_8b_keeps_gemma3_family():
    from ggufloader.core.llm.model_profiles import detect_family
    # llama.cpp reports Gemma-3 8B under the gemma3 arch; a "gemma-3-8b"
    # filename that resolves via name must not collapse to plain gemma2.
    prof, via = detect_family(
        {"architecture": "gemma3", "name": "gemma-3-8b-it"},
        "gemma-3-8b-it-Q4_K_M.gguf")
    assert prof["family"] in ("gemma3", "gemma4"), prof["family"]
    prof2, via2 = detect_family(
        {"architecture": "gemma2", "name": "gemma-2-9b-it"},
        "gemma-2-9b-it-Q4_K_M.gguf")
    assert prof2["family"] == "gemma2", prof2["family"]


def test_unknown_file_never_crashes_returns_generic():
    from ggufloader.core.llm.model_profiles import detect_family
    prof, via = detect_family({}, "mystery-model-9b-q8_0.gguf")
    assert prof["family"] == "generic"
    assert via  # non-empty explanation
