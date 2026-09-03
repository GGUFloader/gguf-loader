"""Task 7: the agent always calls the LLM through one template-aware path.

The graph must route every call through build_llm-style behavior:
single user message, unified stop set, purpose-selected temperatures
(action greedy / answer creative), never raw completion.
"""

import pytest

from ggufloader.core.agent.llm_factory import TEMP_BY_PURPOSE, build_llm
from ggufloader.core.defaults import STOP_TOKENS_UNIFIED


class FakeBackend:
    def __init__(self):
        self.calls = []

    def chat_stream(self, messages, **kw):
        self.calls.append((messages, kw))
        yield "ok"


def test_agent_llm_uses_template_and_stops():
    backend = FakeBackend()
    llm = build_llm(
        backend,
        {"temperature": 0.5, "top_k": 64, "top_p": 0.95,
         "repeat_penalty": 1.05, "max_tokens": 2048},
        purpose="action",
    )
    out = llm("hello")
    assert isinstance(out, str) and "ok" in out
    messages, kw = backend.calls[0]
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert "<end_of_turn>" in kw["stop"]
    assert set(STOP_TOKENS_UNIFIED) == set(kw["stop"])
    assert kw["temperature"] == 0.2  # action temp overrides family temp
    assert kw["max_tokens"] == 2048  # role fallback honored


def test_answer_purpose_uses_answer_temp():
    backend = FakeBackend()
    llm = build_llm(backend, purpose="answer")
    llm("summarize")
    assert backend.calls[0][1]["temperature"] == 0.6
    assert TEMP_BY_PURPOSE["answer"] == 0.6


def test_explicit_temperature_wins():
    backend = FakeBackend()
    llm = build_llm(backend, purpose="action")
    llm("x", temperature=0.9)
    assert backend.calls[0][1]["temperature"] == 0.9


def test_graph_call_llm_passes_purpose_temperature():
    """GraphAgent._call_llm must forward per-purpose temperature."""
    import inspect
    from ggufloader.core.agent.graph_agent import GraphAgent
    src = inspect.getsource(GraphAgent._call_llm)
    assert "purpose" in src
    assert "TEMP_ACTION" in src or "TEMP_ANSWER" in src or "temperature=" in src
