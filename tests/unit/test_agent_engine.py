"""AgentEngine tests using the fake-LLM harness (no real model)."""

from pathlib import Path

import json

from core.agent import AgentEngine, ToolRegistry
from core.agent.agent_engine import extract_json, summarize_directive

WRITE = '{"reasoning": "writing", "tool_calls": [{"tool": "write_file", "parameters": {"path": "notes.md", "content": "Hello"}}]}'
DONE = '{"reasoning": "done", "tool_calls": [], "answer": "All done."}'
READ_MISSING = '{"reasoning": "read", "tool_calls": [{"tool": "read_file", "parameters": {"path": "missing.txt"}}]}'
READ_EXISTS = '{"reasoning": "read ok", "tool_calls": [{"tool": "read_file", "parameters": {"path": "present.txt"}}]}'
LIST_DIR = '{"reasoning": "list", "tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}]}'


class FakeLLM:
    """Scripted LLM: returns responses from a list, then DONE forever."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, prompt, **kwargs):
        self.calls.append(prompt)
        return self.script.pop(0) if self.script else DONE


def test_happy_path(tmp_path: Path) -> None:
    llm = FakeLLM([WRITE, DONE])
    engine = AgentEngine(llm, tmp_path)
    out = engine.process("Create notes.md saying Hello")
    assert (tmp_path / "notes.md").read_text() == "Hello"
    assert out["response"] == "All done."
    assert len(out["tool_results"]) == 1
    assert len(engine.conversation_history) == 2


def test_json_repair(tmp_path: Path) -> None:
    llm = FakeLLM(["not json at all!!!", WRITE, DONE])
    AgentEngine(llm, tmp_path).process("Create notes.md saying Hello")
    assert "not valid JSON" in llm.calls[1]
    assert (tmp_path / "notes.md").read_text() == "Hello"


def test_failure_driven_retry(tmp_path: Path) -> None:
    (tmp_path / "present.txt").write_text("hello world", encoding="utf-8")
    llm = FakeLLM([READ_MISSING, READ_EXISTS, DONE])
    out = AgentEngine(llm, tmp_path).process("Read the file")
    results = out["tool_results"]
    assert len(results) == 2
    assert results[0]["status"] == "error"
    assert results[1]["status"] == "success"
    assert len(llm.calls) == 3  # action + corrective fix + done


def test_step_budget(tmp_path: Path) -> None:
    llm = FakeLLM([WRITE] * 10)
    out = AgentEngine(llm, tmp_path, max_steps=3).process("Do many things")
    # Repeating the identical call is a stale repeat: it runs once, then the
    # run wraps up instead of burning the whole budget on the same write.
    assert len(out["tool_results"]) == 1
    assert len(llm.calls) == 3  # action + stale-repeat round + fallback final response


def test_hedged_repeat_terminates_with_answer(tmp_path: Path) -> None:
    """AgentEngine parity: repeat + answer in one response finishes with the answer."""
    (tmp_path / "notes.txt").write_text("a", encoding="utf-8")
    hedged = (
        '{"reasoning": "list again", '
        '"tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}], '
        '"answer": "The folder contains notes.txt."}'
    )
    llm = FakeLLM([LIST_DIR, hedged])
    out = AgentEngine(llm, tmp_path).process("What files are here?")
    assert out["response"] == "The folder contains notes.txt."
    assert len(out["tool_results"]) == 1
    assert len(llm.calls) == 2


def test_read_content_reaches_model_context(tmp_path: Path) -> None:
    """AgentEngine parity: the file text must reach the model's context."""
    (tmp_path / "vault.txt").write_text("The vault code is 7319-AQUA.", encoding="utf-8")
    read = '{"tool_calls": [{"tool": "read_file", "parameters": {"path": "vault.txt"}}]}'
    prompts = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return read if len(prompts) == 1 else DONE

    AgentEngine(llm, tmp_path).process("Read vault.txt and tell me the code")
    assert "7319-AQUA" in prompts[1]


def test_extract_json_repairs_bare_backslash() -> None:
    """Windows paths like day4\\practice.md are invalid JSON escapes - repaired."""
    data = extract_json('{"tool_calls": [], "answer": "day4\\practice.md"}')
    assert data is not None
    assert data["answer"] == "day4\\practice.md"


def test_extract_json_keeps_valid_escapes() -> None:
    data = extract_json('{"answer": "line1\\nline2 \\"quoted\\""}')
    assert data is not None
    assert data["answer"] == 'line1\nline2 "quoted"'


def test_extract_json_repairs_nested_backslash() -> None:
    data = extract_json('{"tool_calls": [{"tool": "read_file", "parameters": {"path": "day4\\practice.md"}}]}')
    assert data is not None
    assert data["tool_calls"][0]["parameters"]["path"] == "day4\\practice.md"


def _read_entry(path: str) -> dict:
    return {"signature": "read_file:" + json.dumps({"path": path}, sort_keys=True),
            "tool": "read_file"}


def test_summarize_directive_lists_unread(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    directive = summarize_directive("summarize the workspace", tmp_path, [_read_entry("a.md")])
    assert directive is not None
    assert "b.md" in directive
    assert "a.md" not in directive


def test_summarize_directive_all_read_is_none(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    assert summarize_directive("summarize the workspace", tmp_path, [_read_entry("a.md")]) is None


def test_summarize_directive_requires_summarize_intent(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    assert summarize_directive("what is 2+2", tmp_path, []) is None


def test_summarize_directive_named_file_skips(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    assert summarize_directive("summarize a.md", tmp_path, []) is None


def test_summarize_directive_only_readable_files(tmp_path: Path) -> None:
    (tmp_path / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    directive = summarize_directive("summarize the workspace", tmp_path, [])
    assert directive is not None
    assert "a.md" in directive
    assert "pic.png" not in directive


def test_tool_schemas_in_describe(tmp_path: Path) -> None:
    desc = ToolRegistry(tmp_path).describe()
    assert "- path (string, required)" in desc
    assert "- content (string, required)" in desc
    assert "- pattern (string, required)" in desc
    assert "- operation (string, required)" in desc
