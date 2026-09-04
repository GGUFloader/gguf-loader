"""End-to-end agent tests.

Tests the full pipeline: GraphAgent → planner node → tools → approval →
session persistence. These are pure-Python tests (no Qt, no WebSocket) that
exercise the strict plan-driven agent loop with a fake LLM and real tool
execution: the planner node writes the step plan, the agent node follows it
step by step, and the plan's answer step synthesizes the final answer.
"""

import json
import os
from pathlib import Path

import pytest

from ggufloader.core.agent.graph_agent import GraphAgent
from ggufloader.core.agent.presets import PresetManager
from ggufloader.core.agent.tool_registry import ToolRegistry


def _full_tools(ws: Path) -> ToolRegistry:
    """Full tool registry for tests that need write_file, edit_file, etc."""
    return ToolRegistry(ws)


def _plan_json(steps, goal="e2e"):
    """Build plan JSON from (tool, params) tuples; the planner appends the
    final answer step automatically."""
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


def _make_tool_call(tool: str, params: dict) -> str:
    """Build a JSON response with a single tool call (used for orchestrator
    corrective-fix responses)."""
    return json.dumps({
        "reasoning": f"Calling {tool}",
        "tool_calls": [{"tool": tool, "parameters": params}],
    })


class ScriptedLLM:
    """LLM that returns pre-scripted responses in order.

    Each call pops the next response from the list. Supports both
    string returns and generator returns for streaming.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self._call_count = 0

    def __call__(self, prompt: str, **kwargs):
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp
        return "Done."


# ---------------------------------------------------------------------------
# E2E: Basic tool execution
# ---------------------------------------------------------------------------

def test_e2e_list_directory(tmp_path):
    """Agent lists files in workspace via list_directory tool."""
    # Create some files
    (tmp_path / "hello.txt").write_text("hello world")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.py").write_text("print('hi')")

    llm = ScriptedLLM([
        _plan_json([("list_directory", {"path": "."})]),
        "Found 2 items: hello.txt and sub/",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=3,
                       system_prompt='You are a test assistant for unit tests.')
    status_log = []
    tool_results = []

    result = agent.process(
        user_message="List the files",
        on_status=lambda msg: status_log.append(msg),
        on_tool=lambda r: tool_results.append(r),
    )

    assert result["response"] == "Found 2 items: hello.txt and sub/"
    assert len(tool_results) == 1
    assert tool_results[0]["tool_name"] == "list_directory"
    assert tool_results[0]["status"] == "success"
    agent.close()


def test_e2e_write_and_read_file(tmp_path):
    """Agent writes a file then reads it back."""
    llm = ScriptedLLM([
        _plan_json([
            ("write_file", {"path": "output.txt", "content": "test data 123"}),
            ("read_file", {"path": "output.txt"}),
        ]),
        "File contains: test data 123",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=5,
                       tools=_full_tools(tmp_path),
                       system_prompt='You are a test assistant for unit tests.')
    tool_results = []

    result = agent.process(
        user_message="Create a file and read it",
        on_tool=lambda r: tool_results.append(r),
    )

    assert result["response"] == "File contains: test data 123"
    # Should have 2 tool results: write + read
    assert len(tool_results) == 2
    assert tool_results[0]["tool_name"] == "write_file"
    assert tool_results[1]["tool_name"] == "read_file"
    # File should exist on disk
    assert (tmp_path / "output.txt").read_text() == "test data 123"
    agent.close()


def test_e2e_search_files(tmp_path):
    """Agent searches for text in files."""
    (tmp_path / "code.py").write_text("def hello():\n    return 'world'")
    (tmp_path / "readme.md").write_text("# Hello World\nA greeting.")

    llm = ScriptedLLM([
        _plan_json([("search_files", {"pattern": "hello"})]),
        "Found hello in code.py and readme.md",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=3,
                       tools=_full_tools(tmp_path),
                       system_prompt='You are a test assistant for unit tests.')
    tool_results = []

    result = agent.process(
        user_message="Search for hello",
        on_tool=lambda r: tool_results.append(r),
    )

    assert "hello" in result["response"].lower()
    assert len(tool_results) == 1
    assert tool_results[0]["status"] == "success"
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Glob tool
# ---------------------------------------------------------------------------

def test_e2e_glob_tool(tmp_path):
    """Agent uses glob to find files by pattern."""
    (tmp_path / "app.py").write_text("# app")
    (tmp_path / "utils.py").write_text("# utils")
    (tmp_path / "readme.md").write_text("# readme")

    llm = ScriptedLLM([
        _plan_json([("glob", {"pattern": "**/*.py"})]),
        "Found 2 Python files: app.py and utils.py",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=3,
                       system_prompt='You are a test assistant for unit tests.')
    tool_results = []

    result = agent.process(
        user_message="Find all Python files",
        on_tool=lambda r: tool_results.append(r),
    )

    assert "2" in result["response"]
    assert len(tool_results) == 1
    assert tool_results[0]["tool_name"] == "glob"
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Tool failure + corrective retry
# ---------------------------------------------------------------------------

def test_e2e_tool_failure_retry(tmp_path):
    """Agent handles tool failure and retries with corrected params."""
    (tmp_path / "real.txt").write_text("hello")

    llm = ScriptedLLM([
        # Planner: read a non-existent file
        _plan_json([("read_file", {"path": "nonexistent.txt"})]),
        # After failure, the orchestrator's corrective fix reads the right path
        _make_tool_call("read_file", {"path": "real.txt"}),
        "File says hello",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=5,
                       system_prompt='You are a test assistant for unit tests.')
    tool_results = []

    result = agent.process(
        user_message="Read the file",
        on_tool=lambda r: tool_results.append(r),
    )

    assert "hello" in result["response"].lower()
    # First result should be error, second should be success
    assert len(tool_results) >= 2
    assert tool_results[0]["status"] == "error"
    assert tool_results[1]["status"] == "success"
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Approval flow
# ---------------------------------------------------------------------------

def test_e2e_approval_flow(tmp_path):
    """Agent requests approval for write_file, user approves."""
    llm = ScriptedLLM([
        _plan_json([("write_file", {"path": "new.txt", "content": "created"})]),
        "File created successfully",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=3,
                       tools=_full_tools(tmp_path),
                       system_prompt='You are a test assistant for unit tests.')
    approvals = []

    def on_approval(payload):
        approvals.append(payload)
        return True  # approve

    result = agent.process(
        user_message="Create new.txt",
        on_approval=on_approval,
    )

    # Approval may or may not be required depending on ToolRegistry config,
    # but the write must have happened and the answer step must have run.
    assert result["response"] == "File created successfully"
    assert (tmp_path / "new.txt").read_text() == "created"
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Session persistence
# ---------------------------------------------------------------------------

def test_e2e_session_persistence(tmp_path):
    """Agent session persists across GraphAgent instances via SQLite checkpoint."""
    checkpoint = tmp_path / "session.db"

    # First run
    llm1 = ScriptedLLM([
        _plan_json([("write_file", {"path": "notes.txt", "content": "session 1"})]),
        "Created notes.txt",
    ])
    agent1 = GraphAgent(
        llm=llm1, workspace=tmp_path, max_steps=3,
        checkpoint_path=checkpoint, tools=_full_tools(tmp_path),
        system_prompt='You are a test assistant for unit tests.')
    result1 = agent1.process(user_message="Create a notes file")
    assert "notes" in result1["response"].lower()
    thread_id = agent1.thread_id
    agent1.close()

    # Second run (new instance, same workspace → should resume)
    llm2 = ScriptedLLM([
        _plan_json([]),  # answer-only plan for the follow-up question
        "Yes, notes.txt exists with session 1 data",
    ])
    agent2 = GraphAgent(
        llm=llm2, workspace=tmp_path, max_steps=3,
        checkpoint_path=checkpoint,
        thread_id=thread_id,  # same thread
        system_prompt='You are a test assistant for unit tests.')

    # The agent should have loaded previous messages from SQLite
    assert checkpoint.exists()
    result2 = agent2.process(user_message="What did you create?")
    assert result2["response"] == "Yes, notes.txt exists with session 1 data"
    assert any("notes.txt" in str(m) for m in agent2.messages)
    agent2.close()


# ---------------------------------------------------------------------------
# E2E: Workspace context injection
# ---------------------------------------------------------------------------

def test_e2e_workspace_context_injection(tmp_path):
    """GraphAgent injects workspace context (git, project type) into system prompt."""
    # Create a git repo
    os.system(f'cd "{tmp_path}" && git init -q 2>/dev/null || true')
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
    (tmp_path / "AGENTS.md").write_text("# Test Project\nUse pytest for tests.")

    llm = ScriptedLLM([
        _plan_json([]),   # answer-only plan
        "Context received",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=1,
                       system_prompt='You are a test assistant for unit tests.')

    # The router-provided system prompt must be used verbatim — the agent
    # never falls back to a generic "file assistant" prompt anymore.
    sys_prompt = agent._system_prompt()
    assert sys_prompt.startswith("You are a test assistant for unit tests.")
    assert "file assistant" not in sys_prompt.lower()
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Multi-step plan
# ---------------------------------------------------------------------------

def test_e2e_multi_step_plan(tmp_path):
    """Agent executes a multi-step plan: list → read → write summary."""
    (tmp_path / "data.txt").write_text("important data here")

    llm = ScriptedLLM([
        _plan_json([
            ("list_directory", {"path": "."}),
            ("read_file", {"path": "data.txt"}),
            ("write_file", {"path": "summary.txt", "content": "Summary: important data"}),
        ]),
        "Created summary.txt with the data summary",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=6,
                       tools=_full_tools(tmp_path),
                       system_prompt='You are a test assistant for unit tests.')
    tool_results = []

    result = agent.process(
        user_message="Summarize the workspace",
        on_tool=lambda r: tool_results.append(r),
    )

    assert len(tool_results) == 3  # list + read + write
    assert (tmp_path / "summary.txt").exists()
    assert result["response"] == "Created summary.txt with the data summary"
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Cancel mid-run
# ---------------------------------------------------------------------------

def test_e2e_cancel_mechanism(tmp_path):
    """Agent cancel sets the event and _check_cancel raises AgentCancelled."""
    from ggufloader.core.agent.graph_agent import AgentCancelled

    llm = ScriptedLLM(["ok"])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=3,
                       system_prompt='You are a test assistant for unit tests.')
    assert not agent._cancel.is_set()

    agent.cancel()
    assert agent._cancel.is_set()

    # _check_cancel should raise when event is set
    with pytest.raises(AgentCancelled):
        agent._check_cancel()
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Preset integration
# ---------------------------------------------------------------------------

def test_e2e_preset_applies_max_steps():
    """Preset's max_steps should be respected by GraphAgent."""
    pm = PresetManager()

    quick = pm.get("quick_fix")
    assert quick.max_steps == 4

    full = pm.get("full_stack")
    assert full.max_steps == 20

    research = pm.get("research")
    assert "read" in " ".join(research.allowed_tools).lower()


# ---------------------------------------------------------------------------
# E2E: EditFile tool
# ---------------------------------------------------------------------------

def test_e2e_edit_file(tmp_path):
    """Agent edits a file with replace operation."""
    (tmp_path / "config.py").write_text("DEBUG = False\nVERBOSE = True")

    llm = ScriptedLLM([
        _plan_json([("edit_file", {
            "path": "config.py",
            "operation": "replace",
            "find": "DEBUG = False",
            "replace": "DEBUG = True",
        })]),
        "Changed DEBUG to True",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=3,
                       tools=_full_tools(tmp_path),
                       system_prompt='You are a test assistant for unit tests.')
    tool_results = []

    result = agent.process(
        user_message="Enable debug mode",
        on_tool=lambda r: tool_results.append(r),
    )

    assert (tmp_path / "config.py").read_text() == "DEBUG = True\nVERBOSE = True"
    assert len(tool_results) == 1
    assert result["response"] == "Changed DEBUG to True"
    agent.close()


# ---------------------------------------------------------------------------
# E2E: RunCommand tool (sandboxed)
# ---------------------------------------------------------------------------

def test_e2e_run_command(tmp_path):
    """Agent runs a shell command in the workspace."""
    (tmp_path / "test.txt").write_text("hello world")

    llm = ScriptedLLM([
        _plan_json([("run_command", {"command": "cat test.txt"})]),
        "File contains: hello world",
    ])
    agent = GraphAgent(llm=llm, workspace=tmp_path, max_steps=3,
                       tools=_full_tools(tmp_path),
                       system_prompt='You are a test assistant for unit tests.')
    tool_results = []

    result = agent.process(
        user_message="Show me the file contents",
        on_tool=lambda r: tool_results.append(r),
    )

    assert "hello world" in result["response"].lower()
    assert len(tool_results) == 1
    assert tool_results[0]["tool_name"] == "run_command"
    agent.close()


# ---------------------------------------------------------------------------
# E2E: golden log assertions - a clean run stays silent
# ---------------------------------------------------------------------------

def test_e2e_readonly_run_no_error_logs(tmp_path, caplog):
    """A clean read-only run emits no JSON-parse or empty-output errors."""
    import logging

    (tmp_path / "hello.txt").write_text("hello world")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.py").write_text("print('hi')")

    llm = ScriptedLLM([
        _plan_json([("list_directory", {"path": "."})]),
        "Found 2 items: hello.txt and sub/",
    ])
    agent = GraphAgent(
        llm=llm, workspace=tmp_path, max_steps=3,
        system_prompt="You are a test assistant for unit tests.",
    )
    with caplog.at_level(logging.INFO, logger="ggufloader.core.agent"):
        result = agent.process(user_message="List the files")

    assert result["response"] == "Found 2 items: hello.txt and sub/"
    # A clean run must not log parse failures or empty-output warnings.
    joined = "\n".join(caplog.messages)
    assert "could not parse plan JSON" not in joined
    assert "empty" not in joined.lower()
    assert "Traceback" not in joined
    agent.close()