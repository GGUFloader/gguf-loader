"""Tests for phase 6: session export + replay, AGENTS.md generation."""

import json
import tempfile
from pathlib import Path

import pytest

from ggufloader.core.agent.session_replay import SessionReplay, ReplaySession
from ggufloader.core.agent.session_export import SessionExport
from ggufloader.core.agent.agents_md import AgentsMdGenerator
from ggufloader.core.agent.graph_agent import GraphAgent
from ggufloader.core.agent.tool_registry import ToolRegistry


# ---------------------------------------------------------------------------
# SessionReplay
# ---------------------------------------------------------------------------

def test_replay_create_and_record(tmp_path):
    """SessionReplay should create sessions and record steps."""
    replay = SessionReplay(tmp_path)
    session = replay.create_session("test-1", title="Test Session")

    replay.record_user_message("Read README.md")
    replay.record_tool_call("read_file", {"path": "README.md"})
    replay.record_tool_result("read_file", "success")
    replay.record_agent_response("The README says...")

    assert len(session.steps) == 4
    assert session.steps[0].action == "user_message"
    assert session.steps[1].action == "tool_call"
    assert session.steps[2].action == "tool_result"
    assert session.steps[3].action == "agent_response"


def test_replay_save_and_load(tmp_path):
    """Sessions should persist to disk and reload."""
    replay = SessionReplay(tmp_path)
    session = replay.create_session("test-2")
    replay.record_user_message("Hello")
    replay.record_agent_response("Hi there")
    replay.save_session(session)

    loaded = replay.load_session("test-2.json")
    assert loaded is not None
    assert len(loaded.steps) == 2
    assert loaded.steps[0].data["text"] == "Hello"


def test_replay_list_sessions(tmp_path):
    """list_sessions should return saved sessions."""
    replay = SessionReplay(tmp_path)
    s1 = replay.create_session("s1", title="First")
    replay.record_user_message("msg1")
    replay.save_session(s1)

    s2 = replay.create_session("s2", title="Second")
    replay.record_user_message("msg2")
    replay.save_session(s2)

    sessions = replay.list_sessions()
    assert len(sessions) == 2


def test_replay_export_markdown(tmp_path):
    """export_as_markdown should produce readable output."""
    replay = SessionReplay(tmp_path)
    session = replay.create_session("md-test", title="Markdown Export")
    replay.record_user_message("What is Python?")
    replay.record_agent_response("Python is a programming language.")
    md = replay.export_as_markdown(session)

    assert "Python" in md
    assert "User" in md
    assert "Agent" in md


def test_replay_compare_sessions(tmp_path):
    """compare_sessions should find divergence point."""
    replay = SessionReplay(tmp_path)

    a = replay.create_session("a")
    replay.record_user_message("msg1")
    replay.record_agent_response("resp1")
    replay.record_tool_call("read_file", {"path": "foo.py"})
    replay.save_session(a)

    b = replay.create_session("b")
    replay.record_user_message("msg1")
    replay.record_agent_response("resp1")
    replay.record_tool_call("write_file", {"path": "bar.py"})  # different tool
    replay.save_session(b)

    comparison = replay.compare_sessions(a, b)
    assert comparison["identical_prefix"] >= 2  # first two actions match (user_message + agent_response)


# ---------------------------------------------------------------------------
# SessionExport
# ---------------------------------------------------------------------------

def test_export_json(tmp_path):
    """SessionExport should produce valid JSON."""
    exporter = SessionExport(tmp_path)
    session = {"title": "Test", "messages": [{"role": "user", "content": "Hi"}]}
    json_str = exporter.export_json(session)
    data = json.loads(json_str)
    assert data["title"] == "Test"
    assert len(data["messages"]) == 1


def test_export_save_and_load(tmp_path):
    """Exported sessions should persist and reload."""
    exporter = SessionExport(tmp_path)
    session = {"title": "Export Test", "messages": []}
    filepath = exporter.save(session, "test_export.json")
    assert filepath.exists()

    loaded = exporter.load("test_export.json")
    assert loaded is not None
    assert loaded["title"] == "Export Test"


def test_export_markdown(tmp_path):
    """export_markdown should produce readable output."""
    exporter = SessionExport(tmp_path)
    session = {
        "title": "My Session",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ],
    }
    md = exporter.export_markdown(session)
    assert "My Session" in md
    assert "Hello" in md
    assert "Hi!" in md


def test_export_stats(tmp_path):
    """get_session_stats should count correctly."""
    exporter = SessionExport(tmp_path)
    session = {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "Thanks"},
        ],
    }
    stats = exporter.get_session_stats(session)
    assert stats["total_messages"] == 3
    assert stats["user_messages"] == 2
    assert stats["assistant_messages"] == 1


def test_export_list_sessions(tmp_path):
    """list_sessions should return saved exports."""
    exporter = SessionExport(tmp_path)
    exporter.save({"title": "S1", "messages": []}, "s1.json")
    exporter.save({"title": "S2", "messages": []}, "s2.json")

    sessions = exporter.list_sessions()
    assert len(sessions) == 2


# ---------------------------------------------------------------------------
# AGENTS.md Generator
# ---------------------------------------------------------------------------

def test_agents_md_generate_python(tmp_path):
    """Should detect Python project and generate AGENTS.md."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
    (tmp_path / "requirements.txt").write_text("requests\nflask")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_ok(): pass")

    gen = AgentsMdGenerator(tmp_path)
    content = gen.generate()

    assert "Python" in content or "python" in content
    assert "requests" in content
    assert "Agent Instructions" in content


def test_agents_md_generate_node(tmp_path):
    """Should detect Node.js project."""
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "my-app",
        "dependencies": {"express": "^4.18.0"},
    }))

    gen = AgentsMdGenerator(tmp_path)
    content = gen.generate()

    assert "Node" in content or "node" in content
    assert "express" in content


def test_agents_md_write(tmp_path):
    """write() should create AGENTS.md file."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

    gen = AgentsMdGenerator(tmp_path)
    result = gen.write()
    assert result is True
    assert (tmp_path / "AGENTS.md").exists()


def test_agents_md_write_no_overwrite(tmp_path):
    """write() should not overwrite existing AGENTS.md by default."""
    (tmp_path / "AGENTS.md").write_text("# Custom AGENTS.md")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

    gen = AgentsMdGenerator(tmp_path)
    result = gen.write()
    assert result is False
    assert (tmp_path / "AGENTS.md").read_text() == "# Custom AGENTS.md"


def test_agents_md_write_force(tmp_path):
    """write(force=True) should overwrite existing AGENTS.md."""
    (tmp_path / "AGENTS.md").write_text("# Old content")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

    gen = AgentsMdGenerator(tmp_path)
    result = gen.write(force=True)
    assert result is True
    content = (tmp_path / "AGENTS.md").read_text()
    assert "Old content" not in content


def test_agents_md_conventions_detection(tmp_path):
    """Should detect type hints and docstrings in Python code."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
    (tmp_path / "main.py").write_text('''
def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}"
''')

    gen = AgentsMdGenerator(tmp_path)
    content = gen.generate()
    assert "type hint" in content.lower() or "docstring" in content.lower()


# ---------------------------------------------------------------------------
# Tools in registry
# ---------------------------------------------------------------------------

def test_generate_agents_md_tool_in_registry(tmp_path):
    """generate_agents_md tool should be registered."""
    registry = ToolRegistry(tmp_path)
    assert "generate_agents_md" in registry.names()


def test_export_session_tool_in_registry(tmp_path):
    """export_session tool should be registered."""
    registry = ToolRegistry(tmp_path)
    assert "export_session" in registry.names()


def test_generate_agents_md_tool_executes(tmp_path):
    """generate_agents_md tool should work."""
    from ggufloader.core.agent.tool_registry import GenerateAgentsMdTool
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

    tool = GenerateAgentsMdTool(tmp_path)
    result = tool.execute({"force": True})
    assert result["status"] == "success"
    assert "AGENTS.md" in result["result"]


# ---------------------------------------------------------------------------
# GraphAgent wiring
# ---------------------------------------------------------------------------

def test_graph_agent_has_lightweight_core(tmp_path):
    """GraphAgent should have lightweight core attributes."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'

    agent = GraphAgent(llm=fake_llm, workspace=tmp_path)
    assert hasattr(agent, '_context_budget')
    assert hasattr(agent, '_prefix_cache')
    assert hasattr(agent, '_workspace_ctx')
    agent.close()
    agent.close()


def test_graph_agent_process_returns_response(tmp_path):
    """Processing a message should return a response."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "Hello!"}'

    agent = GraphAgent(llm=fake_llm, workspace=tmp_path, max_steps=2)
    result = agent.process(user_message="Hi")
    assert result["response"] == "Hello!"
    agent.close()


def test_graph_agent_total_tool_count(tmp_path):
    """GraphAgent should have all tools including new ones."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'

    from ggufloader.core.agent.tool_registry import ToolRegistry as TR
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path, tools=TR(tmp_path))
    names = agent.tools.names()
    # Phase 2 tools
    assert "glob" in names
    assert "move_file" in names
    # Phase 3 tools
    assert "remember" in names
    assert "recall" in names
    assert "forget" in names
    # Phase 4 tools
    assert "record_correction" in names
    # Phase 6 tools
    assert "generate_agents_md" in names
    assert "export_session" in names
    agent.close()
