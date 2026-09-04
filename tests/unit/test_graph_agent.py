"""GraphAgent (LangGraph StateGraph) tests using the fake-LLM harness.

Strict plan-driven mode: every turn runs ``START → planner → agent ⇄ tools →
END`` as ONE graph. The planner node produces the step plan (or decides no
tools are needed), the agent node follows that plan step by step, and the
plan's answer step synthesizes the final answer. There is no reactive ReAct
loop anymore — when the planner fails, the run ends with a deterministic
wrap-up instead.
"""

import json
import threading
import time
from pathlib import Path

from ggufloader.core.agent import GraphAgent
from ggufloader.core.agent.tool_registry import ToolRegistry


# Full tool registry for tests that need write_file, edit_file, etc.
def _full_tools(ws: Path) -> ToolRegistry:
    return ToolRegistry(ws)  # all tools


def _plan_json(steps, goal="test goal"):
    """Build plan JSON from (tool, params) tuples.

    The planner appends the final answer step automatically (strict
    plan-driven guarantee), so only tool steps need to be listed here.
    """
    plan_steps = [
        {
            "step": i,
            "description": f"Step {i}",
            "tool": tool,
            "parameters": params,
            "depends_on": [],
        }
        for i, (tool, params) in enumerate(steps, 1)
    ]
    return json.dumps({"goal": goal, "steps": plan_steps})


DONE = '{"reasoning": "done", "tool_calls": [], "answer": "All done."}'
READ_EXISTS = ('{"reasoning": "read ok", "tool_calls": '
               '[{"tool": "read_file", "parameters": {"path": "present.txt"}}]}')


class FakeLLM:
    """Scripted LLM: returns responses from a list, then DONE forever."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, prompt, **kwargs):
        self.calls.append(prompt)
        return self.script.pop(0) if self.script else DONE


def test_happy_path(tmp_path: Path) -> None:
    llm = FakeLLM([
        _plan_json([("write_file", {"path": "notes.md", "content": "Hello"})]),
        "All done.",
    ])
    engine = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                        system_prompt='You are a test assistant for unit tests.')
    out = engine.process("Create notes.md saying Hello")
    assert (tmp_path / "notes.md").read_text() == "Hello"
    assert out["response"] == "All done."
    assert len(out["tool_results"]) == 1
    assert not out.get("cancelled")
    # The assistant reply is persisted into the graph's message state.
    assert len(engine.messages) == 2


def test_store_plan_result_reads_orchestrator_result_payload(tmp_path: Path) -> None:
    """Plan-step evidence must be populated from the orchestrator's 'result' key.

    Regression: the answer step in the plan-following path feeds the model
    plan[step]['result'] as evidence; results carry the payload under
    'result' (never 'content'), so an empty store made the model refuse
    with "I do not have access to your local file system".
    """
    llm = FakeLLM([DONE])
    engine = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                        system_prompt='You are a test assistant for unit tests.')
    plan = [
        {"step": 1, "tool": "list_directory", "status": "running"},
        {"step": 2, "tool": "run_command", "status": "running"},
    ]
    results = [
        {"status": "success",
         "result": [{"name": "a.gguf", "type": "file", "size": 100}],
         "tool_name": "list_directory"},
        {"status": "success", "result": "total 6.9G", "tool_name": "run_command"},
    ]
    engine._store_plan_result(plan, 0, results[:1])
    assert plan[0]["status"] == "done"
    assert "a.gguf" in plan[0]["result"]
    engine._store_plan_result(plan, 1, results[1:])
    assert plan[1]["status"] == "done"
    assert "6.9G" in plan[1]["result"]
    # Errors surface too (not as an empty string).
    err = [{"status": "error", "error": "Directory not found", "tool_name": "list_directory"}]
    engine._store_plan_result(plan, 1, err)
    assert plan[1]["status"] == "failed"
    assert "Directory not found" in plan[1]["result"]


def test_json_repair(tmp_path: Path) -> None:
    """The planner retries malformed plan JSON with a repair hint — the
    planner is the only gate to tool execution, so a parse failure must
    never silently drop the run into a fallback."""
    llm = FakeLLM([
        "not json at all!!!",
        _plan_json([("write_file", {"path": "notes.md", "content": "Hello"})]),
        "All done.",
    ])
    out = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                     system_prompt='You are a test assistant for unit tests.').process(
        "Create notes.md saying Hello")
    assert "not valid plan JSON" in llm.calls[1]
    assert (tmp_path / "notes.md").read_text() == "Hello"
    assert out["response"] == "All done."


def test_failure_driven_retry(tmp_path: Path) -> None:
    """A failed plan tool step gets one corrective fix retry via the
    orchestrator, then the answer step synthesizes."""
    (tmp_path / "present.txt").write_text("hello world", encoding="utf-8")
    llm = FakeLLM([
        _plan_json([("read_file", {"path": "missing.txt"})]),
        READ_EXISTS,   # corrective fix from the orchestrator
        "File read ok.",
    ])
    out = GraphAgent(llm, tmp_path,
                     system_prompt='You are a test assistant for unit tests.').process(
        "Read the file")
    results = out["tool_results"]
    assert len(results) == 2
    assert results[0]["status"] == "error"
    assert results[1]["status"] == "success"
    assert len(llm.calls) == 3  # plan + corrective fix + answer


def test_plan_completes_regardless_of_max_steps(tmp_path: Path) -> None:
    """The plan is the budget (capped at 6 steps): max_steps never truncates
    a plan mid-flight — every planned step runs, then the answer step."""
    llm = FakeLLM([
        _plan_json([
            ("write_file", {"path": "a.md", "content": "1"}),
            ("write_file", {"path": "b.md", "content": "2"}),
            ("write_file", {"path": "c.md", "content": "3"}),
        ]),
        "Done with all files.",
    ])
    out = GraphAgent(llm, tmp_path, max_steps=2, tools=_full_tools(tmp_path),
                     system_prompt='You are a test assistant for unit tests.').process(
        "Create three files")
    assert len(out["tool_results"]) == 3
    assert out["response"] == "Done with all files."
    assert (tmp_path / "a.md").exists()
    assert (tmp_path / "b.md").exists()
    assert (tmp_path / "c.md").exists()


def test_streaming_final_answer_tokens(tmp_path: Path) -> None:
    """Only the final-answer synthesis streams tokens (never plan JSON)."""
    chunks = "Here is the summary of what I did."
    tokens: list[str] = []
    calls = []

    def llm(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return _plan_json([("write_file", {"path": "notes.md", "content": "Hello"})])
        return (c for c in chunks)  # final synthesis streams

    engine = GraphAgent(llm, tmp_path, max_steps=3, tools=_full_tools(tmp_path),
                        system_prompt='You are a test assistant for unit tests.')
    out = engine.process("Create notes.md saying Hello", on_token=tokens.append)
    assert "".join(tokens) == chunks
    assert out["response"] == chunks


def test_cancel_stops_run(tmp_path: Path) -> None:
    gate = threading.Event()
    calls = []

    def llm(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return _plan_json([("list_directory", {"path": "."})])
        gate.wait(5)
        return "answer text"

    engine = GraphAgent(llm, tmp_path, max_steps=4,
                        system_prompt='You are a test assistant for unit tests.')
    result: dict = {}

    def run() -> None:
        result.update(engine.process("hello"))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    for _ in range(300):
        if len(calls) >= 2:
            break
        time.sleep(0.01)
    engine.cancel()
    gate.set()
    thread.join(5)
    assert result.get("cancelled") is True


def test_read_content_reaches_model_context(tmp_path: Path) -> None:
    """The model must see the file text, not just a line-count summary."""
    (tmp_path / "vault.txt").write_text("The vault code is 7319-AQUA.", encoding="utf-8")
    prompts = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return _plan_json([("read_file", {"path": "vault.txt"})]) if len(prompts) == 1 else "Done."

    GraphAgent(llm, tmp_path,
               system_prompt='You are a test assistant for unit tests.').process(
        "Read vault.txt and tell me the code")
    assert "7319-AQUA" in prompts[1]
    assert "content:" in prompts[1]


def test_list_names_reach_model_context(tmp_path: Path) -> None:
    """The model must learn what files exist, not just an item count."""
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    (tmp_path / "beta.py").write_text("b", encoding="utf-8")
    prompts = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return _plan_json([("list_directory", {"path": "."})]) if len(prompts) == 1 else "Done."

    GraphAgent(llm, tmp_path,
               system_prompt='You are a test assistant for unit tests.').process(
        "What files exist?")
    assert "alpha.txt" in prompts[1]
    assert "beta.py" in prompts[1]


def test_checkpoint_resume_across_instances(tmp_path: Path) -> None:
    """A new engine with the same workspace resumes the conversation thread."""
    ws = tmp_path / "ws"
    ws.mkdir()
    ckpt = tmp_path / "ckpt.sqlite"
    llm = FakeLLM([
        _plan_json([("write_file", {"path": "notes.md", "content": "Hello"})]),
        "All done.",
        _plan_json([]),   # second turn: answer-only (empty) plan
        "All done.",
    ])

    e1 = GraphAgent(llm, ws, checkpoint_path=ckpt, tools=_full_tools(ws),
                    system_prompt='You are a test assistant for unit tests.')
    out1 = e1.process("Create notes.md saying Hello")
    assert out1["response"] == "All done."
    e1.close()

    # Fresh instance, same workspace + checkpoint file: the conversation
    # (including the assistant reply) is loaded from SQLite.
    e2 = GraphAgent(llm, ws, checkpoint_path=ckpt, tools=_full_tools(ws),
                    system_prompt='You are a test assistant for unit tests.')
    out2 = e2.process("What did you just do?")
    assert out2["response"] == "All done."
    assert any("notes.md" in str(m) for m in e2.messages)
    assert len(e2.messages) == 4  # both exchanges, user + assistant each


def test_plan_answer_step_falls_back_when_model_refuses(tmp_path: Path) -> None:
    """An access-refusal must never be the answer when tool evidence exists:
    the plan answer step renders the evidence deterministically instead."""
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    plan_json = json.dumps({
        "goal": "list then answer",
        "steps": [
            {"step": 1, "description": "List files", "tool": "list_directory",
             "parameters": {"path": "."}, "depends_on": []},
            {"step": 2, "description": "Answer", "tool": None,
             "parameters": {}, "depends_on": [1]},
        ],
    })
    prompts: list[str] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        if len(prompts) == 1:
            return plan_json
        return "I do not have access to your local file system."

    agent = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                       system_prompt="You are a file assistant on this machine.")
    out = agent.process("what is inside this folder?")
    agent.close()

    resp = out["response"]
    assert "notes.txt" in resp
    assert "do not have access" not in resp.lower()


def test_plan_mode_llm_calls_include_system_prompt(tmp_path: Path) -> None:
    """Plan-mode LLM calls must carry the system prompt (identity + rules)."""
    plan_json = json.dumps({
        "goal": "g",
        "steps": [
            {"step": 1, "description": "List", "tool": "list_directory",
             "parameters": {"path": "."}, "depends_on": []},
            {"step": 2, "description": "Answer", "tool": None,
             "parameters": {}, "depends_on": [1]},
        ],
    })
    prompts: list[str] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return plan_json if len(prompts) == 1 else "Everything is listed."

    agent = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                       system_prompt="You are a file assistant running on Gemma 4 12B.")
    out = agent.process("what is here?")
    agent.close()

    assert out["response"]
    assert len(prompts) == 2
    assert "Gemma 4 12B" in prompts[0]  # plan request
    assert "Gemma 4 12B" in prompts[1]  # answer synthesis


def test_general_question_plan_does_not_demand_evidence(tmp_path: Path) -> None:
    """An answer-only plan (general knowledge) must not be told to answer
    'using ONLY the evidence' when no tools ran — that contradiction makes
    the model stall or refuse. The prompt must invite a direct answer."""
    plan_json = json.dumps({
        "goal": "answer directly",
        "steps": [
            {"step": 1, "description": "Provide a clear explanation of AI",
             "tool": None, "parameters": {}, "depends_on": []},
        ],
    })
    prompts: list[str] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return plan_json if len(prompts) == 1 else "AI is the simulation of intelligence in machines."

    agent = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                       system_prompt="You are a helpful assistant.")
    out = agent.process("what is ai?")
    agent.close()

    assert out["response"] == "AI is the simulation of intelligence in machines."
    answer_prompt = prompts[1]
    assert "general-knowledge" in answer_prompt
    assert "no prior results" not in answer_prompt
    assert "using ONLY the evidence" not in answer_prompt
    # Pure-answer calls must not carry the tool catalog either.
    assert "Available tools:" not in answer_prompt


def test_general_answer_omits_preset_mode_text(tmp_path: Path) -> None:
    """Preset mode text ('MODE: Full Stack — commit, run tests') must not
    front pure general-knowledge answers. It belongs with tool planning and
    execution, not Q&A synthesis."""
    plan_json = json.dumps({
        "goal": "answer directly",
        "steps": [
            {"step": 1, "description": "Answer", "tool": None,
             "parameters": {}, "depends_on": []},
        ],
    })
    prompts: list[str] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return plan_json if len(prompts) == 1 else "AI is a field of computer science."

    agent = GraphAgent(
        llm, tmp_path, tools=_full_tools(tmp_path),
        system_prompt="You are a helpful file assistant.",
        preset_prompt=(
            "MODE: Full Stack\n"
            "After code changes, run tests to verify.\n"
            "Commit significant changes with descriptive messages."
        ),
    )
    out = agent.process("what is ai?")
    agent.close()

    assert out["response"] == "AI is a field of computer science."
    # Plan request keeps the mode text (it shapes plan policy)…
    assert "MODE: Full Stack" in prompts[0]
    # …but the pure-answer call must not carry commit/test text in front of it.
    assert "MODE: Full Stack" not in prompts[1]
    assert "run tests to verify" not in prompts[1]
    # The full family + mode + tools prompt still composes.
    assert "MODE: Full Stack" in agent._prompt_builder.system_prompt()


def test_final_response_list_only_refusal_falls_back_to_listing(tmp_path: Path) -> None:
    """_final_response list-only branch: a refusal falls back to the listing."""
    def llm(prompt, **kwargs):
        return "I do not have access to your local file system or any directory."

    agent = GraphAgent(llm, tmp_path,
                       system_prompt="You are a file assistant on this machine.")
    result = agent._final_response(
        [{"role": "user", "content": "what is inside this folder?"}],
        [{"status": "success",
          "result": [{"name": "notes.txt", "type": "file", "size": 5}],
          "tool_name": "list_directory"}],
        lambda _e: None,
    )
    assert "notes.txt" in result
    assert "do not have access" not in result.lower()


def test_plan_answer_evidence_not_truncated_mid_listing(tmp_path: Path) -> None:
    """Directory-listing evidence must reach the answer step whole, not cut to
    a few hundred chars. A hard [:500] slice of a sorted listing drops every
    entry after ~28 names (e.g. 'graph_agent.py') with no ellipsis or count,
    so the model truthfully reports a file is absent when it was simply cut
    off the visible list."""
    # 40 files; the asked-about target sorts LAST so it only survives if the
    # full listing (not the first 500 chars) reaches the synthesis prompt.
    for i in range(39):
        (tmp_path / f"alpha_module_{i:02d}.py").write_text("# filler", encoding="utf-8")
    (tmp_path / "zz_target_module.py").write_text("# target", encoding="utf-8")

    plan_json = json.dumps({
        "goal": "list then answer",
        "steps": [
            {"step": 1, "description": "List files", "tool": "list_directory",
             "parameters": {"path": "."}, "depends_on": []},
            {"step": 2, "description": "Answer", "tool": None,
             "parameters": {}, "depends_on": [1]},
        ],
    })
    prompts: list[str] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return plan_json if len(prompts) == 1 else "The folder contents are listed above."

    agent = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                       system_prompt="You are a file assistant on this machine.")
    out = agent.process("is zz_target_module.py in this folder?")
    agent.close()

    assert out["response"]
    answer_prompt = prompts[1]
    assert "zz_target_module.py" in answer_prompt
    assert "(40 items)" in answer_prompt
    assert "Step 1 (list_directory):" in answer_prompt


def test_planner_is_a_graph_node(tmp_path: Path) -> None:
    """The planner must be a LangGraph node (START → planner → agent → tools),
    not a standalone pre-graph LLM call, so every turn is one graph run."""
    agent = GraphAgent(lambda p, **kw: DONE, tmp_path,
                       tools=_full_tools(tmp_path), system_prompt="x")
    nodes = agent._app.get_graph().nodes
    agent.close()

    assert "planner" in nodes
    assert "agent" in nodes
    assert "tools" in nodes


def test_plan_run_emits_step_status_once(tmp_path: Path) -> None:
    """The '> Step n/m' line must reach the UI exactly once per step.

    Regression: _follow_plan_step emitted the step status through both the
    graph writer AND the on_status callback, so the progress sidebar showed
    every step line twice.
    """
    plan_json = json.dumps({
        "goal": "answer",
        "steps": [{"step": 1, "description": "Answer directly", "tool": None,
                   "parameters": {}, "depends_on": []}],
    })
    prompts: list[str] = []
    statuses: list[str] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return plan_json if len(prompts) == 1 else "AI stands for Artificial Intelligence."

    agent = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                       system_prompt="You are a helpful assistant.")
    out = agent.process("what is ai?", on_status=statuses.append)
    agent.close()

    assert out["response"]
    step_lines = [s for s in statuses if s.startswith("> Step 1/1")]
    assert len(step_lines) == 1, f"expected one step line, got {step_lines!r}"


def test_planner_failure_ends_deterministically(tmp_path: Path) -> None:
    """When the planner produces no plan, the run ends with a deterministic
    wrap-up — no reactive tool loop, no tool execution, no silent second
    agent."""
    prompts: list[str] = []
    statuses: list[str] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        if len(prompts) == 1:
            return "sorry, this is not JSON"
        return "I could not form a plan."

    agent = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                       system_prompt="You are a test assistant.")
    out = agent.process("create notes.md saying Hello", on_status=statuses.append)
    agent.close()

    assert out["response"]
    assert not (tmp_path / "notes.md").exists()   # no tool ran
    assert len(out["tool_results"]) == 0
    assert any("wrapping up" in s for s in statuses), statuses


def test_graph_trace_logs_node_entry_exit_and_turn_summary(
    tmp_path: Path, caplog: object
) -> None:
    """Node tracing: every planner/agent/tools visit plus the per-turn rollup
    is logged at INFO so architecture issues are visible in the server log."""
    import logging

    plan = _plan_json([("list_directory", {"path": "."})])
    llm = FakeLLM([plan, "All done."])
    agent = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                       system_prompt="You are a test assistant.")

    with caplog.at_level(logging.INFO, logger="ggufloader.core.agent.graph_agent"):
        out = agent.process("what is here?")
    agent.close()

    assert out["response"] == "All done."
    lines = [r.message for r in caplog.records]
    graph_lines = [ln for ln in lines if ln.startswith("[graph]")]

    # Planner entered and exited with the produced plan size.
    assert any("planner enter | user=" in ln for ln in graph_lines)
    assert any("planner exit" in ln and "plan=2 steps (1 tool)" in ln for ln in graph_lines)
    # The agent followed the plan step (tool step, then answer step).
    assert any("agent enter" in ln and "plan-step" in ln for ln in graph_lines)
    assert any("agent exit" in ln and "->tools" in ln for ln in graph_lines)
    assert any("agent exit" in ln and "final_answer=9ch" in ln for ln in graph_lines)
    # The tool actually ran.
    assert any("tools enter | pending_calls=['list_directory']" in ln for ln in graph_lines)
    assert any("tools exit" in ln and "list_directory=success" in ln for ln in graph_lines)
    # One per-turn rollup with visit counts.
    turns = [ln for ln in graph_lines if "turn done" in ln]
    assert len(turns) == 1
    assert "visits={'planner': 1, 'agent': 2, 'tools': 1}" in turns[0], turns[0]


def test_graph_trace_can_be_disabled(tmp_path: Path, monkeypatch, caplog) -> None:
    """GGUF_GRAPH_TRACE=0 silences node tracing entirely."""
    import logging

    monkeypatch.setenv("GGUF_GRAPH_TRACE", "0")
    plan = _plan_json([("list_directory", {"path": "."})])
    llm = FakeLLM([plan, "All done."])
    agent = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                       system_prompt="You are a test assistant.")

    with caplog.at_level(logging.INFO, logger="ggufloader.core.agent.graph_agent"):
        agent.process("what is here?")
    agent.close()

    assert not any(r.message.startswith("[graph]") for r in caplog.records)


def test_answer_step_uses_all_completed_step_evidence(tmp_path: Path) -> None:
    """The final answer must synthesize from EVERY completed tool step, not
    just the declared depends_on chain. A plan whose answer depends only on a
    later (empty) search must still see the README a middle step read -
    otherwise the model truthfully reports 'nothing found' while evidence
    it gathered sits unused."""
    (tmp_path / "README.md").write_text("This project does GPU offloading.", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("unrelated text", encoding="utf-8")
    # Answer step 3 depends ONLY on step 2 (the search), which matches
    # nothing with literal 'zzz' - step 1 (the README read) is excluded.
    plan_json = json.dumps({
        "goal": "summarize",
        "steps": [
            {"step": 1, "description": "Read README", "tool": "read_file",
             "parameters": {"path": "README.md"}, "depends_on": []},
            {"step": 2, "description": "Search zzz", "tool": "search_files",
             "parameters": {"pattern": "zzz"}, "depends_on": [1]},
            {"step": 3, "description": "Answer", "tool": None,
             "parameters": {}, "depends_on": [2]},
        ],
    })
    prompts: list[str] = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return plan_json if len(prompts) == 1 else "There is no evidence."

    agent = GraphAgent(llm, tmp_path, tools=_full_tools(tmp_path),
                       system_prompt="You are a file assistant on this machine.")
    out = agent.process("what does this project do?")
    agent.close()

    answer_prompt = prompts[1]
    assert "Step 1 (read_file):" in answer_prompt, "middle-step evidence missing"
    assert "GPU offloading" in answer_prompt, "README content missing from answer evidence"
    assert "Step 2 (search_files):" in answer_prompt
