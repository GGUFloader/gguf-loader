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
READ_A = '{"reasoning": "read a", "tool_calls": [{"tool": "read_file", "parameters": {"path": "a.md"}}]}'
READ_B = '{"reasoning": "read b", "tool_calls": [{"tool": "read_file", "parameters": {"path": "b.md"}}]}'


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
    # Repeating the identical call is a stale repeat: it runs once, then the
    # run wraps up instead of burning the whole budget on the same write.
    assert len(out["tool_results"]) == 1
    assert len(llm.calls) == 3  # action + stale-repeat round + synthesized final


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


def test_hedged_repeat_terminates_with_answer(tmp_path: Path) -> None:
    """Model repeats the identical call AND includes an answer - finish with the answer."""
    (tmp_path / "notes.txt").write_text("a", encoding="utf-8")
    hedged = (
        '{"reasoning": "list again", '
        '"tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}], '
        '"answer": "The folder contains notes.txt."}'
    )
    llm = FakeLLM([LIST_DIR, hedged])
    out = GraphAgent(llm, tmp_path).process("What files are here?")
    assert out["response"] == "The folder contains notes.txt."
    assert len(out["tool_results"]) == 1  # listed once, never re-executed
    assert len(llm.calls) == 2  # no third round


def test_all_stale_repeats_wrap_up_early(tmp_path: Path) -> None:
    """Repeated identical proposals without an answer synthesize immediately."""
    (tmp_path / "notes.txt").write_text("a", encoding="utf-8")
    calls: list[str] = []

    def llm(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return LIST_DIR
        if len(calls) == 2:
            return '{"tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}]}'
        return "The workspace contains notes.txt."

    out = GraphAgent(llm, tmp_path, max_steps=8).process("What files are here?")
    assert len(out["tool_results"]) == 1
    assert len(calls) == 3  # action + repeat + one synthesis (not 9)
    assert "notes.txt" in out["response"]


def test_mixed_repeat_and_new_runs_only_new(tmp_path: Path) -> None:
    """A hedged round with a stale repeat plus a new call executes only the new one."""
    (tmp_path / "notes.txt").write_text("secret", encoding="utf-8")
    calls: list[str] = []

    def llm(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return LIST_DIR
        if len(calls) == 2:
            return (
                '{"tool_calls": ['
                '{"tool": "list_directory", "parameters": {"path": "."}}, '
                '{"tool": "read_file", "parameters": {"path": "notes.txt"}}]}'
            )
        return DONE

    out = GraphAgent(llm, tmp_path).process("What files are here?")
    assert [r["tool_name"] for r in out["tool_results"]] == ["list_directory", "read_file"]
    assert len(calls) == 3


def test_hedged_repeat_with_unescaped_path(tmp_path: Path) -> None:
    """A hedge whose answer contains an unescaped Windows path still parses."""
    (tmp_path / "notes.txt").write_text("a", encoding="utf-8")
    raw = (
        '{"reasoning": "list again", '
        '"tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}], '
        '"answer": "Found day4\\practice.md"}'
    )
    llm = FakeLLM([LIST_DIR, raw])
    out = GraphAgent(llm, tmp_path).process("What files are here?")
    assert out["response"] == "Found day4\\practice.md"
    assert len(out["tool_results"]) == 1  # listed once, never re-executed


def test_summarize_directive_forces_full_read(tmp_path: Path) -> None:
    """A summarize ask must not finish while readable files remain unread."""
    (tmp_path / "a.md").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.md").write_text("beta", encoding="utf-8")
    calls: list[str] = []

    def llm(prompt, **kwargs):
        calls.append(prompt)
        n = len(calls)
        if n == 1:
            return LIST_DIR
        if n == 2:
            return READ_A
        if n == 3:
            return DONE  # answers early - the coverage guard must kick in
        if n == 4:
            return READ_B  # directive round reads the remaining file
        return DONE

    statuses: list[str] = []
    out = GraphAgent(llm, tmp_path).process("summarize the workspace", on_status=statuses.append)
    assert out["response"] == "All done."
    reads = [r for r in out["tool_results"] if r.get("tool_name") == "read_file"]
    assert len(reads) == 2
    assert "IMPORTANT" in calls[3] and "b.md" in calls[3]
    assert any("Reading remaining files" in s for s in statuses)
    assert any("b.md" in s for s in statuses)
    assert len(calls) == 5


def test_non_summarize_ask_gets_no_directive(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.md").write_text("beta", encoding="utf-8")
    calls: list[str] = []

    def llm(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return LIST_DIR
        if len(calls) == 2:
            return READ_A
        return DONE

    out = GraphAgent(llm, tmp_path).process("what does a.md say")
    assert out["response"] == "All done."
    assert len(calls) == 3  # no directive round


def test_legitimate_reread_after_mutation_allowed(tmp_path: Path) -> None:
    """A repeat after a write/edit is NOT stale - the workspace may have changed."""
    calls: list[str] = []

    def llm(prompt, **kwargs):
        calls.append(prompt)
        n = len(calls)
        if n == 1:
            return LIST_DIR
        if n == 2:
            return WRITE
        if n == 3:
            return '{"tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}]}'
        return DONE

    out = GraphAgent(llm, tmp_path).process("List, write a file, then list again")
    tools = [r["tool_name"] for r in out["tool_results"]]
    assert tools.count("list_directory") == 2  # second list ran: a write happened between


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
