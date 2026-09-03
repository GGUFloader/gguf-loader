"""Tests for the template-aware chat path (messages -> create_chat_completion)."""

from ggufloader.core.llm.model_backend import ModelBackend
from ggufloader.core.llm.prompt_builder import PromptBuilder


# ---------------------------------------------------------------------------
# PromptBuilder.build_messages
# ---------------------------------------------------------------------------

def test_build_messages_system_first_user_last():
    pb = PromptBuilder()
    msgs = pb.build_messages([], "hello")
    assert msgs[0]["role"] == "system"
    assert msgs[-1] == {"role": "user", "content": "hello"}
    assert len(msgs) == 2


def test_build_messages_includes_bounded_history():
    pb = PromptBuilder()
    history = [{"role": "user", "content": f"q{i}"} for i in range(20)]
    history.append({"role": "assistant", "content": "a"})
    msgs = pb.build_messages(history, "new q", max_history=8)
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system" and roles[-1] == "user" and roles[-2] == "assistant"
    assert any(m["content"] == "a" for m in msgs)
    assert not any(m.get("content") == "q0" for m in msgs)  # old turns dropped


def test_build_messages_skips_empty_and_tool_roles():
    pb = PromptBuilder()
    history = [
        {"role": "tool", "content": "x"},
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "real"},
    ]
    msgs = pb.build_messages(history, "go")
    assert [m["content"] for m in msgs] == [pb.system_prompt, "real", "go"]


# ---------------------------------------------------------------------------
# ModelBackend.chat_stream (fake llama runtime)
# ---------------------------------------------------------------------------

class FakeChatLlama:
    def __init__(self, chunks):
        self._chunks = chunks
        self.calls = []

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self._chunks)


def _backend_with(fake):
    b = ModelBackend("fake.gguf")
    b._llama = fake
    return b


def test_chat_stream_yields_content_deltas_only():
    fake = FakeChatLlama([
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
        {"choices": []},
        {"choices": [{"delta": {}}]},
    ])
    out = "".join(_backend_with(fake).chat_stream([{"role": "user", "content": "hi"}]))
    assert out == "Hello"


def test_chat_stream_passes_messages_and_no_text_stops():
    fake = FakeChatLlama([])
    msgs = [{"role": "user", "content": "structured answer please"}]
    list(_backend_with(fake).chat_stream(msgs, max_tokens=99, temperature=0.7))
    call = fake.calls[0]
    assert call["messages"] is msgs
    assert call["stream"] is True and call["max_tokens"] == 99
    assert "stop" not in call  # caller decides; service layer adds them


def test_service_layer_injects_template_backstop_stops():
    from ggufloader.core.llm.prompt_builder import CHAT_STOP_TOKENS
    assert "<|im_end|>" in CHAT_STOP_TOKENS      # LFM2 / Qwen / ChatML
    assert "<|eot_id|>" in CHAT_STOP_TOKENS      # Llama 3
    assert "user:" not in CHAT_STOP_TOKENS       # no generic text traps
    assert "###" not in CHAT_STOP_TOKENS         # markdown must survive


def test_chat_requires_loaded_model():
    import pytest
    b = ModelBackend("fake.gguf")
    with pytest.raises(RuntimeError):
        list(b.chat_stream([{"role": "user", "content": "x"}]))


# ---------------------------------------------------------------------------
# Unified stop tokens across every generation path
# ---------------------------------------------------------------------------

def test_unified_stops_everywhere():
    import inspect
    from ggufloader.services import chat_service
    from ggufloader.core import defaults
    src = inspect.getsource(chat_service)
    assert "CHAT_STOP_TOKENS" not in src or "STOP_TOKENS_UNIFIED" in src
    assert "<end_of_turn>" in defaults.STOP_TOKENS_UNIFIED
    assert "user:" not in defaults.STOP_TOKENS_UNIFIED  # bare lowercase trap removed
