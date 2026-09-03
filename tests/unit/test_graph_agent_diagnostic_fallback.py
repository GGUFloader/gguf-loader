from ggufloader.core.agent.graph_agent import GraphAgent, GraphState


class _EmptyLLM:
    def __call__(self, prompt, **kwargs):
        return ""


def test_diagnostic_helper_has_step_info():
    diag = GraphAgent._diagnostic("test reason", step=3, max_steps=5, tool_results=[])
    assert "Done." not in diag
    assert "3/5" not in diag  # step totals come from plan length, never max_steps
    assert "Stopped after 3 steps" in diag
    assert "5-step safety budget" in diag
    assert "test reason" in diag


def test_empty_answer_does_not_return_done_literal():
    agent = GraphAgent(llm=_EmptyLLM(), workspace="/tmp/ws", max_steps=2)
    state: GraphState = {
        "messages": [{"role": "user", "content": "explain"}],
        "tool_results": [],
        "executed_calls": [],
        "step": 2,
        "max_steps": 2,
        "pending_calls": [],
        "final_answer": "",
    }
    out = agent._agent_node(state, writer=lambda _e: None)
    assert out["final_answer"]
    assert "Done." not in out["final_answer"]


def test_process_response_does_not_return_done_literal():
    llm = _EmptyLLM()
    agent = GraphAgent(llm=llm, workspace="/tmp/ws", max_steps=2)
    result = agent.process(user_message="explain")
    assert "Done." not in result["response"]