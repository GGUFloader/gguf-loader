"""Tests for phase 4: plugin loading, error patterns, self-improvement wiring."""

import json
import tempfile
from pathlib import Path

import pytest

from ggufloader.core.agent.graph_agent import GraphAgent
from ggufloader.core.agent.plugin_manager import PluginManager
from ggufloader.core.agent.error_patterns import ErrorPatternDetector
from ggufloader.core.agent.self_improve import SelfImprove
from ggufloader.core.agent.tool_registry import ToolRegistry, RecordCorrectionTool


# ---------------------------------------------------------------------------
# Plugin Manager
# ---------------------------------------------------------------------------

def test_plugin_manager_discover_empty(tmp_path):
    """No plugins in empty directory."""
    pm = PluginManager(tmp_path)
    plugins = pm.discover()
    assert len(plugins) == 0


def test_plugin_manager_discover_json(tmp_path):
    """Discover JSON plugin files."""
    tools_dir = tmp_path / ".ggufloader-tools"
    tools_dir.mkdir()
    (tools_dir / "custom_tool.json").write_text(json.dumps({
        "name": "hello_world",
        "description": "Says hello",
        "command": "echo hello",
    }))
    
    pm = PluginManager(tmp_path)
    plugins = pm.discover()
    assert len(plugins) >= 1
    assert any("custom_tool.json" in str(p) for p in plugins)


def test_plugin_manager_load_json(tmp_path):
    """Load a JSON plugin into a ToolRegistry."""
    tools_dir = tmp_path / ".ggufloader-tools"
    tools_dir.mkdir()
    (tools_dir / "greet.json").write_text(json.dumps({
        "name": "greet",
        "description": "Greet someone",
        "command": "echo hello {name}",
        "parameters": {
            "name": {"type": "string", "description": "Name to greet"}
        },
    }))
    
    registry = ToolRegistry(tmp_path)
    pm = PluginManager(tmp_path)
    results = pm.load_all(registry)
    
    # greet tool should be registered
    assert "greet" in registry.names() or len(results) > 0


# ---------------------------------------------------------------------------
# Error Pattern Detector
# ---------------------------------------------------------------------------

def test_error_pattern_record_and_detect(tmp_path):
    """Recording repeated errors should create detectable patterns."""
    detector = ErrorPatternDetector(tmp_path)
    
    # Record the same error 3 times
    for _ in range(3):
        detector.record_error("syntax", "invalid syntax at line 5",
                             tool="edit_file", file_path="main.py")
    
    patterns = detector.get_patterns(min_occurrences=2)
    assert len(patterns) >= 1
    assert patterns[0].occurrences >= 2


def test_error_pattern_suggestion(tmp_path):
    """After recording a fix, suggestion should be available."""
    detector = ErrorPatternDetector(tmp_path)
    
    detector.record_error("syntax", "missing colon", tool="edit_file")
    detector.record_error("syntax", "missing colon", tool="edit_file")
    
    # Record a fix
    patterns = detector.get_patterns(min_occurrences=2)
    if patterns:
        detector.record_fix(patterns[0].pattern_id, "Always add colons after if/for/def")
        suggestion = detector.get_suggestion("syntax", "missing colon")
        assert suggestion is not None


def test_error_pattern_persistence(tmp_path):
    """Error patterns should persist across instances."""
    detector1 = ErrorPatternDetector(tmp_path)
    for _ in range(3):
        detector1.record_error("runtime", "null pointer", tool="run_command")
    
    detector2 = ErrorPatternDetector(tmp_path)
    patterns = detector2.get_patterns(min_occurrences=2)
    assert len(patterns) >= 1


# ---------------------------------------------------------------------------
# Self-Improve
# ---------------------------------------------------------------------------

def test_self_improve_record_and_get_advice(tmp_path):
    """Recording corrections should produce advice."""
    improve = SelfImprove(tmp_path)
    
    improve.record_correction(
        context="Editing Python files",
        agent_action="Used os.remove()",
        correct_action="Used pathlib.Path.unlink()",
        category="style",
        explanation="This project prefers pathlib over os",
    )
    
    advice = improve.get_advice("editing Python files")
    assert advice is not None
    assert len(advice) > 0


def test_self_improve_persistence(tmp_path):
    """Learning data should persist across instances."""
    improve1 = SelfImprove(tmp_path)
    improve1.record_correction(
        context="Testing",
        agent_action="Ran tests with pytest",
        correct_action="Ran tests with python -m pytest",
        category="style",
    )
    
    improve2 = SelfImprove(tmp_path)
    advice = improve2.get_advice("testing")
    assert advice is not None


# ---------------------------------------------------------------------------
# RecordCorrectionTool
# ---------------------------------------------------------------------------

def test_record_correction_tool(tmp_path):
    """RecordCorrectionTool should store corrections."""
    tool = RecordCorrectionTool(tmp_path)
    result = tool.execute({
        "context": "Editing main.py",
        "agent_action": "Used os.remove()",
        "correct_action": "Used pathlib.Path.unlink()",
        "category": "style",
    })
    assert result["status"] == "success"
    assert "Recorded" in result["result"]


def test_record_correction_tool_in_registry(tmp_path):
    """RecordCorrectionTool should be registered."""
    registry = ToolRegistry(tmp_path)
    assert "record_correction" in registry.names()


# ---------------------------------------------------------------------------
# GraphAgent wiring
# ---------------------------------------------------------------------------

def test_graph_agent_has_plugin_manager(tmp_path):
    """GraphAgent should have a PluginManager."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path)
    assert hasattr(agent, '_plugin_mgr')
    assert isinstance(agent._plugin_mgr, PluginManager)
    agent.close()


def test_graph_agent_has_error_patterns(tmp_path):
    """GraphAgent should have an ErrorPatternDetector."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path)
    assert hasattr(agent, '_error_patterns')
    assert isinstance(agent._error_patterns, ErrorPatternDetector)
    agent.close()


def test_graph_agent_has_self_improve(tmp_path):
    """GraphAgent should have a SelfImprove."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path)
    assert hasattr(agent, '_self_improve')
    assert isinstance(agent._self_improve, SelfImprove)
    agent.close()


def test_graph_agent_system_prompt_includes_error_patterns(tmp_path):
    """System prompt should include error patterns after repeated failures."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    # Pre-populate error patterns
    detector = ErrorPatternDetector(tmp_path)
    for _ in range(3):
        detector.record_error("syntax", "missing colon", tool="edit_file")
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path)
    prompt = agent._system_prompt()
    # Error patterns with 2+ occurrences should be in the prompt
    assert "Error Patterns" in prompt or "missing colon" in prompt
    agent.close()


def test_graph_agent_system_prompt_includes_self_improve(tmp_path):
    """System prompt should include self-improvement advice."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    # Pre-populate corrections with context that matches "general"
    improve = SelfImprove(tmp_path)
    improve.record_correction(
        context="general editing",
        agent_action="Used os.path",
        correct_action="Used pathlib",
        category="style",
        explanation="This project uses pathlib exclusively",
    )
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path)
    prompt = agent._system_prompt()
    # Advice about pathlib should be in the prompt
    assert "pathlib" in prompt
    agent.close()


def test_graph_agent_tool_count_includes_plugins(tmp_path):
    """GraphAgent should have all built-in + memory + correction tools."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path)
    names = agent.tools.names()
    # Built-in tools
    assert "list_directory" in names
    assert "read_file" in names
    assert "write_file" in names
    # Memory tools
    assert "remember" in names
    assert "recall" in names
    assert "forget" in names
    # Correction tool
    assert "record_correction" in names
    # New tools from phase 2
    assert "glob" in names
    assert "move_file" in names
    agent.close()
