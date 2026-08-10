"""ToolRegistry sandbox tests - path escape and roundtrip behavior."""

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
