"""GraphAgent (LangGraph StateGraph) tests using the fake-LLM harness."""

import threading
import time
from pathlib import Path

from core.agent import GraphAgent

WRITE = '{"reasoning": "writing", "tool_calls": [{"tool": "write_file", "parameters": {"path": "notes.md", "content": "Hello"}}]}'
DONE = '{"reasoning": "done", "tool_calls": [], "answer": "All done."}'
LIST_DIR = '{"reasoning": "list", "tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}]}'
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
    engine = GraphAgent(llm, tmp_path)
    out = engine.process("Create notes.md saying Hello")
    assert (tmp_path / "notes.md").read_text() == "Hello"
    assert out["response"] == "All done."
    assert len(out["tool_results"]) == 1
    assert not out.get("cancelled")
    # The assistant reply is persisted into the graph's message state.
    assert len(engine.messages) == 2


def test_json_repair(tmp_path: Path) -> None:
    llm = FakeLLM(["not json at all!!!", WRITE, DONE])
    GraphAgent(llm, tmp_path).process("Create notes.md saying Hello")
    assert "not valid JSON" in llm.calls[1]
    assert (tmp_path / "notes.md").read_text() == "Hello"


def test_failure_driven_retry(tmp_path: Path) -> None:
    (tmp_path / "present.txt").write_text("hello world", encoding="utf-8")
    llm = FakeLLM([READ_MISSING, READ_EXISTS, DONE])
    out = GraphAgent(llm, tmp_path).process("Read the file")
    results = out["tool_results"]
    assert len(results) == 2
    assert results[0]["status"] == "error"
    assert results[1]["status"] == "success"
    assert len(llm.calls) == 3  # action + corrective fix + done


def test_step_budget(tmp_path: Path) -> None:
    llm = FakeLLM([WRITE] * 10)
    out = GraphAgent(llm, tmp_path, max_steps=3).process("Do many things")
    assert len(out["tool_results"]) == 3
    assert len(llm.calls) == 4  # 3 action calls + synthesized final response


def test_streaming_final_answer_tokens(tmp_path: Path) -> None:
    """Only the final-answer synthesis streams tokens (never raw JSON)."""
    chunks = "Here is the summary of what I did."
    tokens: list[str] = []
    calls = []

    def llm(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return WRITE
        if len(calls) == 2:
            return '{"tool_calls": [], "answer": ""}'
        return (c for c in chunks)  # final synthesis streams

    engine = GraphAgent(llm, tmp_path, max_steps=3)
    out = engine.process("Create notes.md saying Hello", on_token=tokens.append)
    assert "".join(tokens) == chunks
    assert out["response"] == chunks


def test_cancel_stops_run(tmp_path: Path) -> None:
    gate = threading.Event()
    calls = []

    def llm(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return LIST_DIR
        gate.wait(5)
        return DONE

    engine = GraphAgent(llm, tmp_path, max_steps=4)
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
    read = '{"tool_calls": [{"tool": "read_file", "parameters": {"path": "vault.txt"}}]}'
    prompts = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return read if len(prompts) == 1 else DONE

    GraphAgent(llm, tmp_path).process("Read vault.txt and tell me the code")
    assert "7319-AQUA" in prompts[1]
    assert "content:" in prompts[1]


def test_list_names_reach_model_context(tmp_path: Path) -> None:
    """The model must learn what files exist, not just an item count."""
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    (tmp_path / "beta.py").write_text("b", encoding="utf-8")
    list_dir = '{"tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}]}'
    prompts = []

    def llm(prompt, **kwargs):
        prompts.append(prompt)
        return list_dir if len(prompts) == 1 else DONE

    GraphAgent(llm, tmp_path).process("What files exist?")
    assert "alpha.txt" in prompts[1]
    assert "beta.py" in prompts[1]


def test_checkpoint_resume_across_instances(tmp_path: Path) -> None:
    """A new engine with the same workspace resumes the conversation thread."""
    ws = tmp_path / "ws"
    ws.mkdir()
    ckpt = tmp_path / "ckpt.sqlite"
    llm = FakeLLM([WRITE, DONE, DONE])

    e1 = GraphAgent(llm, ws, checkpoint_path=ckpt)
    out1 = e1.process("Create notes.md saying Hello")
    assert out1["response"] == "All done."
    e1.close()

    # Fresh instance, same workspace + checkpoint file: the conversation
    # (including the assistant reply) is loaded from SQLite.
    e2 = GraphAgent(llm, ws, checkpoint_path=ckpt)
    out2 = e2.process("What did you just do?")
    assert out2["response"] == "All done."
    assert "notes.md" in llm.calls[2]
    assert len(e2.messages) == 4  # both exchanges, user + assistant each
