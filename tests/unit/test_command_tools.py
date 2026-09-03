"""Sandboxed command/git tools and the approval interrupt flow."""

import subprocess
import sys
from pathlib import Path

import pytest

from ggufloader.core.agent import GraphAgent, ToolRegistry
from ggufloader.core.agent.tool_registry import tool_content_for_context


def _full_tools(ws):
    return ToolRegistry(ws)

RUN_CMD = ('{"tool_calls": [{"tool": "run_command", "parameters": '
           '{"command": "echo approved > marker.txt"}}]}')
GIT_COMMIT = ('{"tool_calls": [{"tool": "git", "parameters": '
              '{"args": ["commit", "-m", "test"]}}]}')
DONE = '{"tool_calls": [], "answer": "All done."}'


class FakeLLM:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, prompt, **kwargs):
        self.calls.append(prompt)
        return self.script.pop(0) if self.script else DONE


# ----------------------------------------------------------------------
# run_command tool
# ----------------------------------------------------------------------
def test_run_command_runs_in_workspace(tmp_path: Path) -> None:
    reg = ToolRegistry(tmp_path)
    out = reg.execute("run_command", {"command": "echo hello > rel.txt"})
    assert out["status"] == "success"
    assert (tmp_path / "rel.txt").exists()
    assert "hello" in (tmp_path / "rel.txt").read_text(encoding="utf-8", errors="replace")


def test_run_command_reports_failure(tmp_path: Path) -> None:
    reg = ToolRegistry(tmp_path)
    out = reg.execute("run_command", {"command": "exit 3"})
    assert out["status"] == "error"
    assert out["returncode"] == 3


def test_run_command_times_out(tmp_path: Path) -> None:
    reg = ToolRegistry(tmp_path)
    out = reg.execute(
        "run_command",
        {"command": f'"{sys.executable}" -c "import time; time.sleep(5)"', "timeout": 1},
    )
    assert out["status"] == "error"
    assert "timed out" in out["error"]


# ----------------------------------------------------------------------
# git tool
# ----------------------------------------------------------------------
def test_git_read_only_and_write_gating(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, text=True)
    reg = ToolRegistry(tmp_path)

    status = reg.execute("git", {"args": ["status"]})
    assert status["status"] == "success"

    assert reg.requires_approval("git", {"args": ["status"]}) is False
    assert reg.requires_approval("git", {"args": ["diff"]}) is False
    assert reg.requires_approval("git", {"args": ["commit", "-m", "x"]}) is True
    assert reg.requires_approval("git", {"args": ["push"]}) is True
    assert reg.requires_approval("git", {"args": ["reset", "--hard"]}) is True


# ----------------------------------------------------------------------
# Approval gating in the registry
# ----------------------------------------------------------------------
def test_requires_approval_defaults(tmp_path: Path) -> None:
    reg = ToolRegistry(tmp_path)
    assert reg.requires_approval("run_command", {"command": "ls"}) is True
    assert reg.requires_approval("write_file", {"path": "a.txt", "content": "x"}) is False
    assert reg.requires_approval("read_file", {"path": "a.txt"}) is False
    assert reg.requires_approval("nope", {}) is False


# ----------------------------------------------------------------------
# GraphAgent approval interrupt flow
# ----------------------------------------------------------------------
def test_approval_approved_runs_command(tmp_path: Path) -> None:
    approvals: list[dict] = []
    llm = FakeLLM([RUN_CMD, DONE])
    engine = GraphAgent(llm, tmp_path, plan=False, tools=_full_tools(tmp_path), system_prompt='You are a test assistant for unit tests.')
    out = engine.process(
        "Create marker.txt via shell",
        on_approval=lambda payload: (approvals.append(payload), True)[1],
    )
    assert (tmp_path / "marker.txt").exists()
    assert out["response"] == "All done."
    assert len(approvals) == 1
    assert approvals[0]["type"] == "approval"
    assert approvals[0]["call"]["tool"] == "run_command"
    results = out["tool_results"]
    assert len(results) == 1
    assert results[0]["status"] == "success"


def test_approval_denied_skips_command(tmp_path: Path) -> None:
    approvals: list[dict] = []
    llm = FakeLLM([RUN_CMD, DONE])
    engine = GraphAgent(llm, tmp_path, plan=False, tools=_full_tools(tmp_path), system_prompt='You are a test assistant for unit tests.')
    out = engine.process(
        "Create marker.txt via shell",
        on_approval=lambda payload: (approvals.append(payload), False)[1],
    )
    assert not (tmp_path / "marker.txt").exists()
    assert len(approvals) == 1
    results = out["tool_results"]
    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert "denied" in results[0]["error"]


def test_approval_git_write_is_gated(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, text=True)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=tmp_path, capture_output=True, text=True,
    )

    approvals: list[dict] = []
    llm = FakeLLM([GIT_COMMIT, DONE])
    engine = GraphAgent(llm, tmp_path, plan=False, tools=_full_tools(tmp_path), system_prompt='You are a test assistant for unit tests.')
    engine.process("Commit the changes", on_approval=lambda p: (approvals.append(p), True)[1])
    assert len(approvals) == 1
    assert approvals[0]["call"]["tool"] == "git"


def test_interrupt_does_not_run_untouched(tmp_path: Path) -> None:
    """Non-sensitive runs never suspend for approval."""
    llm = FakeLLM(['{"tool_calls": [{"tool": "write_file", "parameters": {"path": "n.txt", "content": "hi"}}]}', DONE])
    approvals: list[dict] = []
    engine = GraphAgent(llm, tmp_path, plan=False, tools=_full_tools(tmp_path), system_prompt='You are a test assistant for unit tests.')
    out = engine.process(
        "Write n.txt",
        on_approval=lambda p: (approvals.append(p), True)[1],
    )
    assert (tmp_path / "n.txt").read_text() == "hi"
    assert approvals == []
    assert out["response"] == "All done."


@pytest.mark.skipif(sys.platform == "win32", reason="exit code semantics differ on Windows")
def test_git_tool_reports_error_outside_repo(tmp_path: Path) -> None:
    reg = ToolRegistry(tmp_path)
    out = reg.execute("git", {"args": ["status"]})
    assert out["status"] == "error"


# ----------------------------------------------------------------------
# Content feedback helper (read/list/search payload reaches the model)
# ----------------------------------------------------------------------
def test_content_helper_includes_payload() -> None:
    text = tool_content_for_context(
        {"tool_name": "read_file", "status": "success", "result": "hello world"}
    )
    assert text is not None and "hello world" in text

    names = tool_content_for_context(
        {"tool_name": "list_directory", "status": "success",
         "result": [{"name": "a.txt"}, {"name": "b.py"}]}
    )
    assert names is not None and "a.txt" in names and "b.py" in names

    paths = tool_content_for_context(
        {"tool_name": "search_files", "status": "success", "result": ["src/x.py"]}
    )
    assert paths is not None and "src/x.py" in paths

    # Non-contentful tools keep a plain summary (helper returns None).
    assert tool_content_for_context(
        {"tool_name": "write_file", "status": "success", "result": "ok"}
    ) is None


def test_content_helper_truncates() -> None:
    big = "x" * 5000
    out = tool_content_for_context({"tool_name": "read_file", "status": "success", "result": big})
    assert out is not None
    assert len(out) < 4200
    assert out.endswith("…")
