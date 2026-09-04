"""Task 7: the agent always calls the LLM through one template-aware path.

The graph must route every call through build_llm-style behavior:
single user message, unified stop set, purpose-selected temperatures
(action greedy / answer creative), never raw completion.
"""

import pytest

from ggufloader.core.agent.llm_factory import TEMP_BY_PURPOSE, build_llm
from ggufloader.core.defaults import STOP_TOKENS_UNIFIED, TEMP_ACTION, TEMP_ANSWER


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
    assert kw["temperature"] == TEMP_ACTION  # action temp overrides family temp
    assert kw["max_tokens"] == 2048  # role fallback honored


def test_answer_purpose_uses_answer_temp():
    backend = FakeBackend()
    llm = build_llm(backend, purpose="answer")
    llm("summarize")
    assert backend.calls[0][1]["temperature"] == TEMP_ANSWER
    assert TEMP_BY_PURPOSE["answer"] == TEMP_ANSWER


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


def test_build_llm_streams_deltas_to_on_token():
    """build_llm must push each generated delta through its on_token sink
    while still returning the joined string. Without this, prose answers are
    generated in total silence and the UI freezes on the status step."""
    class MultiDeltaBackend:
        def __init__(self):
            self.calls = []

        def chat_stream(self, messages, **kw):
            self.calls.append((messages, kw))
            yield "Hello "
            yield "world"
            yield "!"

    backend = MultiDeltaBackend()
    received: list[str] = []
    llm = build_llm(backend, on_token=received.append)
    out = llm("hi")

    assert out == "Hello world!"  # joined string unchanged
    assert received == ["Hello ", "world", "!"]  # each delta streamed live

    # A per-call on_chunk overrides the build-time sink (GraphAgent routes
    # its process-level token callback per answer call this way).
    per_call: list[str] = []
    llm("hi", on_chunk=per_call.append)
    assert per_call == ["Hello ", "world", "!"]


def test_answer_calls_stream_tokens_through_on_chunk(tmp_path):
    """Prose-answer synthesis must forward the agent's on_token callback as
    on_chunk so deltas reach the UI mid-generation."""
    import json
    from pathlib import Path

    from ggufloader.core.agent import GraphAgent
    from ggufloader.core.agent.tool_registry import ToolRegistry

    def tools(ws: Path) -> ToolRegistry:
        return ToolRegistry(ws)

    plan_json = json.dumps({
        "goal": "answer",
        "steps": [
            {"step": 1, "description": "Answer", "tool": None,
             "parameters": {}, "depends_on": []},
        ],
    })
    prompts: list[str] = []
    streamed: list[str] = []
    call_kwargs: list[dict] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        call_kwargs.append(kwargs)
        if len(prompts) == 1:
            return plan_json
        # Simulate a streaming callable: push chunks, then return joined text.
        chunks = ["AI is ", "the simulation ", "of intelligence."]
        for c in chunks:
            kwargs.get("on_chunk", lambda _t: None)(c)
        return "".join(chunks)

    agent = GraphAgent(llm, tmp_path, tools=tools(tmp_path),
                       system_prompt="You are a helpful assistant.")
    out = agent.process(
        "what is ai?",
        on_token=streamed.append,
    )
    agent.close()

    assert out["response"] == "AI is the simulation of intelligence."
    # The answer call (call #2) carried on_chunk and it streamed every delta.
    assert "on_chunk" in call_kwargs[1]
    assert streamed == ["AI is ", "the simulation ", "of intelligence."]


def test_plan_call_streams_to_reasoning_not_bubble(tmp_path):
    """Planner deltas must reach the UI as reasoning (sidebar thinking step),
    never as chat-bubble tokens — the plan is JSON protocol text, not the
    user's answer. The answer call still streams into the bubble."""
    import json
    from pathlib import Path

    from ggufloader.core.agent import GraphAgent
    from ggufloader.core.agent.tool_registry import ToolRegistry

    def tools(ws: Path) -> ToolRegistry:
        return ToolRegistry(ws)

    plan_json = json.dumps({
        "goal": "answer",
        "steps": [{"step": 1, "description": "Answer", "tool": None,
                    "parameters": {}, "depends_on": []}],
    })
    prompts: list[str] = []
    reasoning: list[str] = []
    bubble: list[str] = []
    call_kwargs: list[dict] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        call_kwargs.append(kwargs)
        if len(prompts) == 1:
            # Plan call: simulate a streaming callable pushing plan deltas.
            for c in ['{"goal": "answer", ', '"steps": []}']:
                kwargs.get("on_chunk", lambda _t: None)(c)
            return plan_json
        # Answer call: deltas belong in the chat bubble.
        for c in ["AI is ", "intelligence."]:
            kwargs.get("on_chunk", lambda _t: None)(c)
        return "AI is intelligence."

    agent = GraphAgent(llm, tmp_path, tools=tools(tmp_path),
                       system_prompt="You are a helpful assistant.")
    out = agent.process("what is ai?", on_token=bubble.append,
                        on_plan_stream=reasoning.append)
    agent.close()

    assert out["response"] == "AI is intelligence."
    # Plan deltas landed in the reasoning sink, not the bubble…
    assert "".join(reasoning) == '{"goal": "answer", "steps": []}'
    assert bubble == ["AI is ", "intelligence."]
    # …and each call was wired to the right sink (compare __self__ because
    # bound-method objects are recreated on every attribute access).
    assert call_kwargs[0]["on_chunk"].__self__ is reasoning
    assert call_kwargs[1]["on_chunk"].__self__ is bubble


def test_reasoning_callback_strips_json_fence():
    """The planner's ```json fence must never reach the thinking card — the
    reasoning stream starts at the plan JSON itself."""
    import asyncio

    from ggufloader.core.agent.agent_transport import AgentTransport

    sent: list = []

    class _WS:
        async def send_event(self, event):
            sent.append(event)

    transport = AgentTransport(_WS(), asyncio.new_event_loop(),
                               message_id="m1", preset_id="p")
    cb = transport.make_reasoning_callback()
    # Fence split across chunks, then the JSON plan forms.
    cb("```json")
    cb('\n{"goal": "a')
    cb('nswer", "steps": []}')

    contents = [e.get("content") for e in sent if e.get("type") == "reasoning"]
    joined = "".join(contents)
    assert joined.startswith('{"goal": "answer"'), repr(joined)
    assert "```" not in joined
    assert joined.count('{"goal"') == 1  # fence never forwarded

    # Once live, chunks pass straight through.
    cb("tail")
    assert sent[-1]["content"] == "tail"
