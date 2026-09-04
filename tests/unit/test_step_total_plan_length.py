"""Regression: step totals in status events always come from the plan length.

The step counter the UI shows (e.g. "Step 1/3") must be driven by the
created plan. ``max_steps`` is a safety budget, not a plan, so it must
never surface as the step denominator — a 12-step preset budget must not
show "Step 1/12" for a 3-step plan.

Covers every emission point:
  - ``_follow_plan_step`` (plan-following path)
  - ``_agent_node`` (reactive fallback, no plan)
  - ``_dispatch_event`` (step event → status string)
  - ``AgentTransport._handle_status`` (status → frontend events)
  - a full ``GraphAgent.process()`` run
"""

import json
from pathlib import Path

import pytest

from ggufloader.core.agent.agent_transport import AgentTransport
from ggufloader.core.agent.graph_agent import GraphAgent, GraphState

TEST_SYSTEM_PROMPT = "You are a test assistant for unit tests."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scripted_llm(plan_json: str, finish: str = "All done."):
    """LLM that answers a plan request with ``plan_json`` then finishes."""
    calls = {"n": 0}

    def llm(prompt, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return plan_json
        if "Evidence" in prompt or "User asked" in prompt:
            return finish
        return json.dumps({"reasoning": "done", "tool_calls": [], "answer": finish})

    return llm


def _status_collector():
    statuses: list = []

    def on_status(msg: str) -> None:
        statuses.append(msg)

    return statuses, on_status


# ---------------------------------------------------------------------------
# _follow_plan_step: total = len(plan), never max_steps
# ---------------------------------------------------------------------------

def test_follow_plan_step_status_uses_plan_length_not_max_steps():
    llm = _scripted_llm(json.dumps({"goal": "g", "steps": []}))
    agent = GraphAgent(
        llm=llm, workspace="/tmp/ws", max_steps=12,
        system_prompt=TEST_SYSTEM_PROMPT,
    )
    plan = [
        {"step": 1, "description": "list files", "tool": "list_directory",
         "parameters": {"path": "."}, "depends_on": []},
        {"step": 2, "description": "answer", "tool": None,
         "parameters": {}, "depends_on": [1]},
        {"step": 3, "description": "verify", "tool": "list_directory",
         "parameters": {"path": "."}, "depends_on": [2]},
    ]
    writer_events: list = []

    agent._follow_plan_step(
        plan, 0, step=0, max_steps=12,
        messages=[{"role": "user", "content": "hi"}],
        tool_results=[], writer=writer_events.append,
    )

    step_event = next(e for e in writer_events if e.get("event") == "step")
    assert step_event["max"] == 3, step_event          # plan length
    assert step_event["max"] != 12, step_event         # never max_steps
    status = next(e["text"] for e in writer_events if e.get("event") == "status")
    assert status.startswith("> Step 1/3"), status
    assert "/12" not in status, status


# ---------------------------------------------------------------------------
# _agent_node reactive fallback: step event has no max_steps denominator
# ---------------------------------------------------------------------------

def test_no_plan_emits_no_step_event():
    """No plan → the agent node ends the run without any step event (there
    is no reactive loop anymore), so no budget total can ever leak."""

    def llm(prompt, **kwargs):
        return json.dumps({"reasoning": "r", "tool_calls": [], "answer": "ok"})

    agent = GraphAgent(
        llm=llm, workspace="/tmp/ws", max_steps=12,
        system_prompt=TEST_SYSTEM_PROMPT,
    )
    state: GraphState = {
        "messages": [{"role": "user", "content": "hi"}],
        "tool_results": [],
        "executed_calls": [],
        "step": 0,
        "max_steps": 12,
        "pending_calls": [],
        "final_answer": "",
    }
    writer_events: list = []

    agent._agent_node(state, writer=writer_events.append)

    step_events = [e for e in writer_events if e.get("event") == "step"]
    assert not step_events, f"no step event expected without a plan: {step_events}"
    # The run ends deterministically with an answer instead.
    assert any(e.get("event") == "status" for e in writer_events)


# ---------------------------------------------------------------------------
# _dispatch_event: status text carries a total only when max is provided
# ---------------------------------------------------------------------------

def test_dispatch_step_without_max_has_no_slash():
    statuses, on_status = _status_collector()
    agent = GraphAgent(
        llm=lambda prompt, **kw: "{}", workspace="/tmp/ws",
        system_prompt=TEST_SYSTEM_PROMPT,
    )
    agent._on_status = on_status

    agent._dispatch_event({"event": "step", "step": 3})

    assert statuses == ["Step 3"], statuses
    assert all("/" not in s for s in statuses)


def test_dispatch_step_with_max_uses_provided_total():
    statuses, on_status = _status_collector()
    agent = GraphAgent(
        llm=lambda prompt, **kw: "{}", workspace="/tmp/ws",
        system_prompt=TEST_SYSTEM_PROMPT,
    )
    agent._on_status = on_status

    agent._dispatch_event({"event": "step", "step": 1, "max": 4})

    assert statuses == ["Step 1/4"], statuses


def test_dispatch_step_ignores_agent_max_steps_when_max_missing():
    """Regression: payloads without 'max' must not default to self.max_steps."""
    statuses, on_status = _status_collector()
    agent = GraphAgent(
        llm=lambda prompt, **kw: "{}", workspace="/tmp/ws", max_steps=12,
        system_prompt=TEST_SYSTEM_PROMPT,
    )
    agent._on_status = on_status

    agent._dispatch_event({"event": "step", "step": 2})

    assert statuses == ["Step 2"], statuses
    assert "/12" not in statuses[0]


# ---------------------------------------------------------------------------
# AgentTransport._handle_status: frontend-facing events
# ---------------------------------------------------------------------------

class _FakeWebSocket:
    def __init__(self):
        self.sent: list = []

    def send_event(self, event: dict) -> None:
        self.sent.append(event)


@pytest.fixture()
def transport():
    import asyncio
    ws = _FakeWebSocket()
    return AgentTransport(ws, asyncio.new_event_loop(), message_id="m1", preset_id="full_stack"), ws


def test_transport_plan_step_event_total_is_plan_length(transport):
    agent, ws = transport
    agent._handle_status("> Step 1/3: list files")

    phase_events = [e for e in ws.sent if e.get("type") == "agent_phase"]
    assert phase_events, "no agent_phase event"
    plan_step = phase_events[0].get("plan_step")
    assert plan_step == {"current": 1, "total": 3, "description": "list files"}, plan_step
    assert plan_step["total"] != 12


def test_transport_suppresses_bare_step_total_from_progress(transport):
    """'Step 3/12' (no '>' prefix) carries a budget total and must not show."""
    agent, ws = transport
    agent._handle_status("Step 3/12")

    announces = [e for e in ws.sent if e.get("type") == "progress_announce"]
    assert all("Step 3/12" not in (e.get("content") or "") for e in announces), ws.sent


def test_transport_keeps_bare_step_without_total(transport):
    """'Step 3' (no denominator) is a harmless progress counter — keep it."""
    agent, ws = transport
    agent._handle_status("Step 3")

    announces = [e for e in ws.sent if e.get("type") == "progress_announce"]
    assert any("Step 3" == (e.get("content") or "").strip() for e in announces), ws.sent


# ---------------------------------------------------------------------------
# End-to-end: a full GraphAgent.process() run never shows max_steps as total
# ---------------------------------------------------------------------------

def test_end_to_end_status_totals_never_equal_max_steps(tmp_path: Path):
    """Plan of 2 steps with max_steps=12 → every 'Step N/M' uses /2."""
    plan_json = json.dumps({
        "goal": "list then answer",
        "steps": [
            {"step": 1, "description": "List workspace files", "tool": "list_directory",
             "parameters": {"path": "."}, "depends_on": []},
            {"step": 2, "description": "Answer", "tool": None,
             "parameters": {}, "depends_on": [1]},
        ],
    })
    llm = _scripted_llm(plan_json, finish="Two files found.")

    agent = GraphAgent(
        llm=llm, workspace=tmp_path, max_steps=12,
        system_prompt=TEST_SYSTEM_PROMPT,
    )
    statuses, on_status = _status_collector()

    result = agent.process(user_message="what is in this workspace?", on_status=on_status)
    agent.close()

    step_msgs = [s for s in statuses if "Step " in s]
    assert step_msgs, f"no step statuses seen: {statuses}"

    # Any 'Step N/M' must carry the plan length (2), never the 12-step budget.
    for s in step_msgs:
        assert "/12" not in s, f"max_steps leaked into status: {s!r}"
    assert any("Step 1/2" in s for s in step_msgs), step_msgs
    assert any("Step 2/2" in s for s in step_msgs), step_msgs

    # The run must still complete with a final answer.
    assert result.get("response") or result.get("final_answer") or result.get("answer")
