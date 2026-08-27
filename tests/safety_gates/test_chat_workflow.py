"""HIGH Gate: Chat Workflow - 95%+ pass rate."""
import pytest
from ggufloader.core.llm.model_profiles import FAMILY_PROFILES, _template_supports_system
from ggufloader.core.llm.prompt_builder import PromptBuilder

def test_family_profiles_loaded():
    assert len(FAMILY_PROFILES) > 0

def test_family_has_required_keys():
    for profile in FAMILY_PROFILES:
        assert "family" in profile
        assert "archs" in profile
        assert isinstance(profile["archs"], tuple)

def test_mistral_no_system():
    mistral = [p for p in FAMILY_PROFILES if "mistral" in p["family"]]
    assert len(mistral) > 0
    assert mistral[0]["supports_system_prompt"] is False

def test_prompt_builder_produces_messages():
    builder = PromptBuilder()
    msgs = builder.build_messages([], "hello", system_prompt="test")
    assert isinstance(msgs, list)
    assert len(msgs) >= 1
