from ggufloader.core.agent.graph_agent import GraphAgent, GraphState


class _StepBumpingLLM:
    def __init__(self):
        self.called = 0

    def __call__(self, prompt, **kwargs):
        self.called += 1
        if self.called == 1:
            return '{"reasoning":"planning","estimated_steps":15,"tool_calls":[{"tool":"list_directory","parameters":{}}],"answer":""}'
        return '{"reasoning":"done","tool_calls":[],"answer":"ok"}'


def test_agent_node_persists_bumped_max_steps():
    llm = _StepBumpingLLM()
    agent = GraphAgent(llm=llm, workspace="/tmp/ws", max_steps=4, system_prompt='You are a test assistant for unit tests.')
    state: GraphState = {
        "messages": [{"role": "user", "content": "hi"}],
        "tool_results": [],
        "executed_calls": [],
        "step": 0,
        "max_steps": 4,
        "pending_calls": [],
        "final_answer": "",
    }
    out = agent._agent_node(state, writer=lambda _e: None)
    assert out.get("max_steps", 4) >= 15