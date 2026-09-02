from ggufloader.core.agent.graph_agent import GraphAgent, GraphState


class _ReasoningOnlyLLM:
    """Returns reasoning-only JSON on early calls; answers in plain text
    once re-asked."""
    def __init__(self):
        self.called = 0

    def __call__(self, prompt, **kwargs):
        self.called += 1
        if self.called == 1:
            return "AI stands for Artificial Intelligence - it is the field of computer science focused on building systems that can perform tasks requiring human-like reasoning."


def test_reasoning_only_triggers_reask_and_produces_answer():
    llm = _ReasoningOnlyLLM()
    agent = GraphAgent(llm=llm, workspace="/tmp/ws", max_steps=10)
    tool_results = [
        {"tool_name": "list_directory", "status": "success", "content": "history.json"}
    ]
    answer = agent._reask_for_answer(
        [{"role": "user", "content": "what is ai"}],
        tool_results,
        writer=lambda _e: None,
    )
    assert "Artificial Intelligence" in answer
    assert "tool_calls" not in answer
    assert "{" not in answer


def test_answer_field_present_detection():
    llm = _ReasoningOnlyLLM()
    agent = GraphAgent(llm=llm, workspace="/tmp/ws", max_steps=10)
    assert agent._answer_field_present({"answer": "ok", "tool_calls": []}) is True
    assert agent._answer_field_present({"tool_calls": [], "answer": ""}) is False
    assert agent._answer_field_present({"tool_calls": []}) is False
    assert agent._answer_field_present({"answer": "   "}) is False


class _ReaskReturnsJsonLLM:
    """Reask still returns JSON-thinking wrapped in a fence."""
    def __init__(self):
        self.called = 0

    def __call__(self, prompt, **kwargs):
        self.called += 1
        if self.called == 1:
            return '```json\n{"reasoning":"thinking","answer":"Photosynthesis is how plants make food from sunlight.","tool_calls":[]}\n```'


def test_reask_recovers_answer_from_json_wrapped_response():
    llm = _ReaskReturnsJsonLLM()
    agent = GraphAgent(llm=llm, workspace="/tmp/ws", max_steps=10)
    answer = agent._reask_for_answer(
        [{"role": "user", "content": "what is photosynthesis"}],
        [{"tool_name": "list_directory", "status": "success", "content": "a.txt"}],
        writer=lambda _e: None,
    )
    assert "Photosynthesis" in answer
    assert "{" not in answer
    assert "tool_calls" not in answer