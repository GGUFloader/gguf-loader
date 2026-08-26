"""Batch 5: run_python tool, followup extraction, feedback persistence."""

from ggufloader.core.agent.tool_registry import RunPythonTool, ToolRegistry
from ggufloader.core.llm.followups import extract_questions
from ggufloader.core.sessions import SessionStore


# ---------------------------------------------------------------------------
# H: run_python agent tool
# ---------------------------------------------------------------------------

def test_run_python_success(tmp_path):
    tool = RunPythonTool(tmp_path)
    res = tool.execute({"code": "print('hello ' + 'world')"})
    assert res["status"] == "success" and res["exit_code"] == 0
    assert "hello world" in (res.get("result") or "")


def test_run_python_error_surfaces_stderr(tmp_path):
    tool = RunPythonTool(tmp_path)
    res = tool.execute({"code": "import sys; sys.exit('boom')"})
    assert res["status"] == "error"
    assert "boom" in res.get("error", "")


def test_run_python_requires_approval():
    assert RunPythonTool(tmp_path_factory()).requires_approval({}) is True


def tmp_path_factory():
    import tempfile
    return tempfile.mkdtemp()


def test_run_python_empty_code():
    tool = RunPythonTool(tmp_path_factory())
    res = tool.execute({"code": "   "})
    assert res["status"] == "error"


def test_registry_includes_python_and_approval():
    reg = ToolRegistry(tmp_path_factory())
    assert "run_python" in reg.names()
    assert reg.requires_approval("run_python", {}) is True


# ---------------------------------------------------------------------------
# D3: follow-up question extraction
# ---------------------------------------------------------------------------

def test_extract_questions_basic_and_limit():
    text = ("Sure. What is 2+2? Where can I buy widgets? "
            "Why is the sky blue? Who knows? And a statement.")
    qs = extract_questions(text)
    assert len(qs) == 3
    assert all(q.endswith("?") for q in qs)


def test_extract_questions_dedupes_case_insensitive():
    text = "What is love? what is LOVE? Nothing else."
    assert extract_questions(text) == ["What is love?"]


def test_extract_questions_none():
    assert extract_questions("No questions here at all.") == []


# ---------------------------------------------------------------------------
# D1/K5: feedback persisted on newest matching assistant message
# ---------------------------------------------------------------------------

def test_set_last_assistant_feedback_targets_newest_match(tmp_path):
    store = SessionStore(tmp_path / "chats")
    s = store.create()
    store.append_message(s, "user", "q")
    store.append_message(s, "assistant", "answer one")
    store.append_message(s, "user", "again")
    store.append_message(s, "assistant", "answer two")
    assert store.set_last_assistant_feedback(s, "answer one", "down",
                                             note="say X instead") is True
    msgs = s["messages"]
    assert msgs[1]["feedback"] == "down"
    assert msgs[1]["feedback_note"] == "say X instead"
    assert "feedback" not in msgs[3]


def test_thinking_ms_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "chats")
    s = store.create()
    store.append_message(s, "user", "hard question")
    store.append_message(s, "assistant", "42")
    s["messages"][-1]["thinking_ms"] = 4210
    store.save(s)
    loaded = store.load(s["id"])
    assert loaded["messages"][-1]["thinking_ms"] == 4210
