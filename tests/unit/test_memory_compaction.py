"""Tests for memory persistence and context compaction in the agent."""

import json
import tempfile
from pathlib import Path

import pytest

from ggufloader.core.agent.memory_persistence import MemoryPersistence, MemoryEntry
from ggufloader.core.agent.context_budget import ContextBudget, estimate_tokens
from ggufloader.core.agent.context_compactor import ContextCompactor
from ggufloader.core.agent.graph_agent import GraphAgent
from ggufloader.core.agent.tool_registry import ToolRegistry


# ---------------------------------------------------------------------------
# MemoryPersistence
# ---------------------------------------------------------------------------

def test_memory_remember_and_recall(tmp_path):
    """Store and retrieve a memory by key."""
    mem = MemoryPersistence(tmp_path)
    mem.remember("project_type", "Python FastAPI app", category="context")
    
    results = mem.recall("project_type")
    assert len(results) == 1
    assert results[0].key == "project_type"
    assert results[0].value == "Python FastAPI app"
    assert results[0].category == "context"


def test_memory_update_existing_key(tmp_path):
    """Updating an existing key should replace, not duplicate."""
    mem = MemoryPersistence(tmp_path)
    mem.remember("temp", "0.7")
    mem.remember("temp", "0.3")
    
    results = mem.recall("temp")
    assert len(results) == 1
    assert results[0].value == "0.3"


def test_memory_forget(tmp_path):
    """Forget removes a memory."""
    mem = MemoryPersistence(tmp_path)
    mem.remember("to_delete", "yes")
    assert mem.forget("to_delete") is True
    assert mem.recall("to_delete") == []


def test_memory_persists_across_instances(tmp_path):
    """Memories survive creating a new MemoryPersistence instance."""
    mem1 = MemoryPersistence(tmp_path)
    mem1.remember("persistent_key", "persistent_value")
    
    mem2 = MemoryPersistence(tmp_path)
    results = mem2.recall("persistent_key")
    assert len(results) == 1
    assert results[0].value == "persistent_value"


def test_memory_context_format(tmp_path):
    """get_context should produce a structured string."""
    mem = MemoryPersistence(tmp_path)
    mem.remember("language", "Python", category="fact")
    mem.remember("style", "type hints", category="preference")
    
    ctx = mem.get_context()
    assert "Python" in ctx
    assert "type hints" in ctx
    assert "Known Facts" in ctx or "User Preferences" in ctx


def test_memory_max_cap(tmp_path):
    """Memory store should enforce a cap."""
    mem = MemoryPersistence(tmp_path)
    for i in range(250):
        mem.remember(f"key_{i}", f"value_{i}")
    # Should be capped (not 250)
    assert mem.count() < 250


def test_memory_categories(tmp_path):
    """Different categories should be tracked separately."""
    mem = MemoryPersistence(tmp_path)
    mem.remember("fact1", "some fact", category="fact")
    mem.remember("pref1", "some pref", category="preference")
    mem.remember("corr1", "some correction", category="correction")
    
    facts = mem.get_all(category="fact")
    prefs = mem.get_all(category="preference")
    corrs = mem.get_all(category="correction")
    
    assert len(facts) == 1
    assert len(prefs) == 1
    assert len(corrs) == 1


# ---------------------------------------------------------------------------
# ContextBudget
# ---------------------------------------------------------------------------

def test_context_budget_ok():
    """Under budget should return 'ok'."""
    budget = ContextBudget(total_budget=8192)
    messages = [{"role": "user", "content": "Hello"}]
    assert budget.check_budget(messages) == "ok"


def test_context_budget_summarize():
    """Approaching budget should return 'summarize'."""
    budget = ContextBudget(total_budget=1000, system_prompt_tokens=100)
    # Create messages that use ~85% of budget (850 tokens ≈ 3400 chars)
    long_msg = "x" * 3400
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": long_msg},
        {"role": "assistant", "content": long_msg},
    ]
    strategy = budget.check_budget(messages)
    assert strategy in ("summarize", "trim", "drop")


def test_context_budget_compact():
    """Compaction should reduce message count."""
    budget = ContextBudget(total_budget=1000, system_prompt_tokens=100)
    messages = [{"role": "system", "content": "sys"}]
    for i in range(20):
        messages.append({"role": "user", "content": f"msg {i} " + "x" * 500})
        messages.append({"role": "assistant", "content": f"reply {i} " + "y" * 500})
    
    compacted = budget.compact(messages)
    assert len(compacted) < len(messages)
    # System message should be preserved
    assert compacted[0]["role"] == "system"


def test_context_budget_stats():
    """Stats should report correct values."""
    budget = ContextBudget(total_budget=4096, system_prompt_tokens=500)
    stats = budget.get_stats()
    assert stats["total_budget"] == 4096
    assert stats["system_tokens"] == 500
    assert stats["available"] == 3596


# ---------------------------------------------------------------------------
# ContextCompactor
# ---------------------------------------------------------------------------

def test_compactor_under_limit():
    """Under limit should return messages unchanged."""
    compactor = ContextCompactor(max_history_chars=10000)
    messages = [{"role": "user", "content": "short"}]
    result = compactor.compact(messages)
    assert result == messages


def test_compactor_over_limit():
    """Over limit should summarize old messages."""
    compactor = ContextCompactor(max_history_chars=500, keep_recent=2)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "a" * 200},
        {"role": "assistant", "content": "b" * 200},
        {"role": "user", "content": "c" * 200},
        {"role": "assistant", "content": "d" * 200},
        {"role": "user", "content": "e" * 200},
        {"role": "assistant", "content": "f" * 200},
    ]
    result = compactor.compact(messages)
    assert len(result) < len(messages)
    # First message should be a summary
    assert "Context summary" in result[0]["content"] or result[0]["role"] == "system"


# ---------------------------------------------------------------------------
# Memory tools
# ---------------------------------------------------------------------------

def test_graph_agent_has_context_budget(tmp_path):
    """GraphAgent should have a ContextBudget instance."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path, system_prompt='You are a test assistant for unit tests.')
    assert hasattr(agent, '_context_budget')
    assert isinstance(agent._context_budget, ContextBudget)
    agent.close()


def test_graph_agent_requires_router_system_prompt(tmp_path):
    """Agent must fail loudly when no router system prompt is provided."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path, )
    with pytest.raises(RuntimeError, match="No system prompt provided"):
        agent._system_prompt()
    agent.close()


def test_graph_agent_uses_router_system_prompt(tmp_path):
    """Router-provided system prompt is used verbatim (no fallback rewrite)."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path,                        system_prompt="You are a test assistant for unit tests.")
    prompt = agent._system_prompt()
    assert prompt.startswith("You are a test assistant for unit tests.")
    agent.close()


def test_graph_agent_compacts_on_long_history(tmp_path):
    """GraphAgent should compact long conversation histories."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'
    
    agent = GraphAgent(llm=fake_llm, workspace=tmp_path, system_prompt='You are a test assistant for unit tests.')
    # Set a very small budget
    agent._context_budget.set_budget(total=500, system_tokens=50)
    
    # Simulate a long conversation
    agent.messages = [{"role": "system", "content": "You are helpful."}]
    for i in range(20):
        agent.messages.append({"role": "user", "content": f"Question {i}: " + "x" * 200})
        agent.messages.append({"role": "assistant", "content": f"Answer {i}: " + "y" * 200})
    
    status_msgs = []
    result = agent.process(
        user_message="final question",
        on_status=lambda msg: status_msgs.append(msg),
    )
    
    # Should have triggered compaction
    compact_msgs = [m for m in status_msgs if "ompacting" in m]
    assert len(compact_msgs) > 0
    agent.close()


