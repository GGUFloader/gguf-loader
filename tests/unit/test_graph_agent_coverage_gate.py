from ggufloader.core.agent.graph_agent import GraphAgent, GraphState


class _ShortAnswerLLM:
    def __call__(self, prompt, **kwargs):
        return '{"reasoning":"x","tool_calls":[],"answer":"ok"}'


def test_short_answer_with_no_tool_results_triggers_directive_for_summarize(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    llm = _ShortAnswerLLM()
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=10)
    state: GraphState = {
        "messages": [{"role": "user", "content": "summarize the project"}],
        "tool_results": [],
        "executed_calls": [],
        "step": 0,
        "max_steps": 10,
        "directive": "",
        "directive_rounds": 0,
        "pending_calls": [],
        "final_answer": "",
    }
    out = agent._finish_or_direct(
        state, state["messages"], "ok", "", 0,
        writer=lambda _e: None, max_steps=10,
    )
    assert out.get("final_answer") == ""
    assert out.get("directive")


def test_short_answer_with_tool_evidence_accepted():
    agent = GraphAgent(llm=_ShortAnswerLLM(), workspace="/tmp/ws", max_steps=10)
    state: GraphState = {
        "messages": [{"role": "user", "content": "list files"}],
        "tool_results": [{"tool_name": "list_directory", "status": "success", "content": "a.txt b.txt"}],
        "executed_calls": [],
        "step": 0,
        "max_steps": 10,
        "directive": "",
        "directive_rounds": 0,
        "pending_calls": [],
        "final_answer": "",
    }
    out = agent._finish_or_direct(
        state, state["messages"], "a.txt b.txt", "", 0,
        writer=lambda _e: None, max_steps=10,
    )
    assert out.get("final_answer") == "a.txt b.txt"