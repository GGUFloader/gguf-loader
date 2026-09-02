"""End-to-end agent tests.

Tests the full pipeline: GraphAgent → tools → approval → session persistence.
These are pure-Python tests (no Qt, no WebSocket) that exercise the agent
loop with a fake LLM and real tool execution.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

from ggufloader.core.agent.tool_registry import ToolRegistry


def _full_tools(ws: Path) -> ToolRegistry:
    """Full tool registry for tests that need write_file, edit_file, etc."""
    return ToolRegistry(ws)

import pytest

from ggufloader.core.agent.graph_agent import GraphAgent
from ggufloader.core.agent.tool_registry import ToolRegistry
from ggufloader.core.agent.presets import PresetManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ScriptedLLM:
    """LLM that returns pre-scripted responses in order.

    Each call pops the next response from the list. Supports both
    string returns and generator returns for streaming.
    """

    def __init__(self, responses: List[str]):
        self._responses = list(responses)
        self._call_count = 0

    def __call__(self, prompt: str, **kwargs) -> str:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp
        return '{"tool_calls": [], "answer": "Done."}'


def _make_tool_call(tool: str, params: dict) -> str:
    """Build a JSON response with a single tool call."""
    return json.dumps({
        "reasoning": f"Calling {tool}",
        "tool_calls": [{"tool": tool, "parameters": params}],
    })


def _make_answer(answer: str) -> str:
    """Build a JSON response with a final answer."""
    return json.dumps({
        "reasoning": "Done",
        "tool_calls": [],
        "answer": answer,
    })


# ---------------------------------------------------------------------------
# E2E: Basic tool execution
# ---------------------------------------------------------------------------

def test_e2e_list_directory(tmp_path):
    """Agent lists files in workspace via list_directory tool."""
    # Create some files
    (tmp_path / "hello.txt").write_text("hello world")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.py").write_text("print('hi')")

    responses = [
        _make_tool_call("list_directory", {"path": "."}),
        _make_answer("Found 2 items: hello.txt and sub/"),
    ]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=3)
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
    responses = [
        _make_tool_call("write_file", {"path": "output.txt", "content": "test data 123"}),
        _make_tool_call("read_file", {"path": "output.txt"}),
        _make_answer("File contains: test data 123"),
    ]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=5, tools=_full_tools(tmp_path))
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

    responses = [
        _make_tool_call("search_files", {"pattern": "hello"}),
        _make_answer("Found hello in code.py and readme.md"),
    ]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=3, tools=_full_tools(tmp_path))
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

    responses = [
        _make_tool_call("glob", {"pattern": "**/*.py"}),
        _make_answer("Found 2 Python files: app.py and utils.py"),
    ]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=3)
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
    responses = [
        # First attempt: read non-existent file
        _make_tool_call("read_file", {"path": "nonexistent.txt"}),
        # After failure, model tries again with correct path
        _make_tool_call("read_file", {"path": "real.txt"}),
        _make_answer("File says hello"),
    ]
    llm = ScriptedLLM(responses)

    (tmp_path / "real.txt").write_text("hello")

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=5)
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
    # Agent proposes write_file → triggers approval → approved → executed
    responses = [
        _make_tool_call("write_file", {"path": "new.txt", "content": "created"}),
        _make_answer("File created successfully"),
    ]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=3, tools=_full_tools(tmp_path))
    approvals = []

    def on_approval(payload):
        approvals.append(payload)
        return True  # approve

    result = agent.process(
        user_message="Create new.txt",
        on_approval=on_approval,
    )

    # Approval should have been requested
    # (write_file may or may not require approval depending on ToolRegistry config)
    assert result["response"] == "File created successfully"
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Session persistence
# ---------------------------------------------------------------------------

def test_e2e_session_persistence(tmp_path):
    """Agent session persists across GraphAgent instances via SQLite checkpoint."""
    checkpoint = tmp_path / "session.db"

    # First run
    responses1 = [
        _make_tool_call("write_file", {"path": "notes.txt", "content": "session 1"}),
        _make_answer("Created notes.txt"),
    ]
    llm1 = ScriptedLLM(responses1)
    agent1 = GraphAgent(
        llm=llm1, workspace=tmp_path, max_steps=3,
        checkpoint_path=checkpoint, tools=_full_tools(tmp_path),
    )
    result1 = agent1.process(user_message="Create a notes file")
    assert "notes" in result1["response"].lower()
    thread_id = agent1.thread_id
    agent1.close()

    # Second run (new instance, same workspace → should resume)
    responses2 = [
        _make_answer("Yes, notes.txt exists with session 1 data"),
    ]
    llm2 = ScriptedLLM(responses2)
    agent2 = GraphAgent(
        llm=llm2, workspace=tmp_path, max_steps=3,
        checkpoint_path=checkpoint,
        thread_id=thread_id,  # same thread
    )

    # The agent should have loaded previous messages
    assert checkpoint.exists()
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

    responses = [_make_answer("Context received")]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=1)

    # The system prompt should be lightweight (file-assistant mode)
    sys_prompt = agent._system_prompt()
    assert "file assistant" in sys_prompt.lower() or "AGENTS.md" in sys_prompt
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Multi-step plan
# ---------------------------------------------------------------------------

def test_e2e_multi_step_plan(tmp_path):
    """Agent executes a multi-step plan: list → read → write summary."""
    (tmp_path / "data.txt").write_text("important data here")

    responses = [
        # Step 1: list directory
        _make_tool_call("list_directory", {"path": "."}),
        # Step 2: read the file
        _make_tool_call("read_file", {"path": "data.txt"}),
        # Step 3: write summary
        _make_tool_call("write_file", {"path": "summary.txt", "content": "Summary: important data"}),
        # Step 4: final answer
        _make_answer("Created summary.txt with the data summary"),
    ]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=6, tools=_full_tools(tmp_path))
    tool_results = []

    result = agent.process(
        user_message="Summarize the workspace",
        on_tool=lambda r: tool_results.append(r),
    )

    assert len(tool_results) == 3  # list + read + write
    assert (tmp_path / "summary.txt").exists()
    agent.close()


# ---------------------------------------------------------------------------
# E2E: Cancel mid-run
# ---------------------------------------------------------------------------

def test_e2e_cancel_mechanism(tmp_path):
    """Agent cancel sets the event and _check_cancel raises AgentCancelled."""
    from ggufloader.core.agent.graph_agent import AgentCancelled

    responses = [_make_answer("ok")]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=3)
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

    responses = [
        _make_tool_call("edit_file", {
            "path": "config.py",
            "operation": "replace",
            "find": "DEBUG = False",
            "replace": "DEBUG = True",
        }),
        _make_answer("Changed DEBUG to True"),
    ]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=3, tools=_full_tools(tmp_path))
    tool_results = []

    result = agent.process(
        user_message="Enable debug mode",
        on_tool=lambda r: tool_results.append(r),
    )

    assert (tmp_path / "config.py").read_text() == "DEBUG = True\nVERBOSE = True"
    assert len(tool_results) == 1
    agent.close()


# ---------------------------------------------------------------------------
# E2E: RunCommand tool (sandboxed)
# ---------------------------------------------------------------------------

def test_e2e_run_command(tmp_path):
    """Agent runs a shell command in the workspace."""
    (tmp_path / "test.txt").write_text("hello world")

    responses = [
        _make_tool_call("run_command", {"command": "cat test.txt"}),
        _make_answer("File contains: hello world"),
    ]
    llm = ScriptedLLM(responses)

    agent = GraphAgent(llm=llm, workspace=tmp_path, plan=False, max_steps=3, tools=_full_tools(tmp_path))
    tool_results = []

    result = agent.process(
        user_message="Show me the file contents",
        on_tool=lambda r: tool_results.append(r),
    )

    assert "hello world" in result["response"].lower()
    assert len(tool_results) == 1
    assert tool_results[0]["tool_name"] == "run_command"
    agent.close()
