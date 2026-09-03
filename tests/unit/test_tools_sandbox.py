"""ToolRegistry sandbox tests - path escape and roundtrip behavior."""

import tempfile
from pathlib import Path

from ggufloader.core.agent import ToolRegistry


def test_path_escape_is_blocked(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    result = registry.execute("read_file", {"path": "../outside.txt"})
    assert result["status"] == "error"
    assert "escapes" in result["error"]


def test_write_read_roundtrip(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    written = registry.execute("write_file", {"path": "sub/a.txt", "content": "x"})
    assert written["status"] == "success"
    assert (tmp_path / "sub" / "a.txt").exists()
    read = registry.execute("read_file", {"path": "sub/a.txt"})
    assert read["status"] == "success"
    assert read["result"] == "x"


def test_edit_replace(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("hello world", encoding="utf-8")
    registry = ToolRegistry(tmp_path)
    result = registry.execute(
        "edit_file", {"path": "f.txt", "operation": "replace", "find": "world", "replace": "there"}
    )
    assert result["status"] == "success"
    assert result["changes_made"] == 1
    assert (tmp_path / "f.txt").read_text() == "hello there"


def test_unknown_tool_returns_error(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    result = registry.execute("definitely_not_a_tool", {})
    assert result["status"] == "error"
    assert "Unknown tool" in result["error"]


# ---------------------------------------------------------------------------
# One tool universe (Task 10): deprecated aliases must be blocked by the
# read-only presets, and the system prompt must list the live registry set.
# ---------------------------------------------------------------------------

def test_research_blocks_python_aliases() -> None:
    """The read-only research preset blocks every code-execution alias."""
    from ggufloader.core.agent.presets import PRESETS
    blocked = set(PRESETS["research"].blocked_tools)
    assert {"python_interpreter", "batch_execute", "move_file"} <= blocked


def test_code_review_blocks_python_aliases() -> None:
    """The read-only code_review preset blocks every code-execution alias."""
    from ggufloader.core.agent.presets import PRESETS
    blocked = set(PRESETS["code_review"].blocked_tools)
    assert {"python_interpreter", "batch_execute", "move_file"} <= blocked


def test_prompt_lists_live_tools() -> None:
    """System prompt lists the live registry tools, never a stale subset."""
    from ggufloader.core.agent.prompt_builder import PromptBuilder
    ws = Path(tempfile.mkdtemp())
    pb = PromptBuilder(
        ws,
        ToolRegistry(ws),
        system_prompt_override="You are an assistant.",
    )
    prompt = pb.system_prompt()
    assert "batch_execute" in prompt or "move_file" in prompt


def test_python_interpreter_is_deprecated_alias() -> None:
    """python_interpreter now aliases run_python (approval-gated, one schema)."""
    from ggufloader.core.agent.tool_registry import RunPythonTool, PythonInterpreterTool
    assert issubclass(PythonInterpreterTool, RunPythonTool)
    assert PythonInterpreterTool.name == "python_interpreter"
    # Same approval gate as run_python - the sandboxed no-approval
    # interpreter is gone (it was a fake sandbox with full interpreter
    # access).
    import warnings
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        registry = ToolRegistry(tempfile.mkdtemp())
        result = registry.execute("python_interpreter", {"code": "print(1)"})
    assert result["status"] == "success"
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert registry.requires_approval("python_interpreter", {"code": "print(1)"}) is True
