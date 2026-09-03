from ggufloader.core.agent.graph_agent import GraphAgent, GraphState


class _UnderestimatingLLM:
    """Says estimated_steps=2 but actually needs many more."""
    def __init__(self):
        self.called = 0

    def __call__(self, prompt, **kwargs):
        self.called += 1
        if self.called == 1:
            return '{"reasoning":"start","estimated_steps":2,"tool_calls":[{"tool":"list_directory","parameters":{}}],"answer":""}'
        return '{"reasoning":"done","tool_calls":[],"answer":"finished"}'


def test_max_steps_never_shrinks_from_underestimate():
    llm = _UnderestimatingLLM()
    agent = GraphAgent(llm=llm, workspace="/tmp/ws", max_steps=20, system_prompt='You are a test assistant for unit tests.')
    state: GraphState = {
        "messages": [{"role": "user", "content": "hi"}],
        "tool_results": [],
        "executed_calls": [],
        "step": 0,
        "max_steps": 20,
        "pending_calls": [],
        "final_answer": "",
    }
    out = agent._agent_node(state, writer=lambda _e: None)
    assert out.get("max_steps", 20) == 20, "max_steps must not be reduced below the configured budget"