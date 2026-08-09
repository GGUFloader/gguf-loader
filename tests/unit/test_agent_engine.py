"""AgentEngine tests using the fake-LLM harness (no real model)."""

from pathlib import Path

from core.agent import AgentEngine, ToolRegistry

WRITE = '{"reasoning": "writing", "tool_calls": [{"tool": "write_file", "parameters": {"path": "notes.md", "content": "Hello"}}]}'
DONE = '{"reasoning": "done", "tool_calls": [], "answer": "All done."}'
READ_MISSING = '{"reasoning": "read", "tool_calls": [{"tool": "read_file", "parameters": {"path": "missing.txt"}}]}'
READ_EXISTS = '{"reasoning": "read ok", "tool_calls": [{"tool": "read_file", "parameters": {"path": "present.txt"}}]}'


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
    assert len(out["tool_results"]) == 3
    assert len(llm.calls) == 4  # 3 action calls + fallback final response


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


def test_tool_schemas_in_describe(tmp_path: Path) -> None:
    desc = ToolRegistry(tmp_path).describe()
    assert "- path (string, required)" in desc
    assert "- content (string, required)" in desc
    assert "- pattern (string, required)" in desc
    assert "- operation (string, required)" in desc
