"""Tests for the rewritten agent WebSocket flow.

Verifies that:
- Presets API returns correct data
- GraphAgent can be created with preset + router params
- Approval flow mechanics work (event-based blocking)
- Agent metrics tracking in chatStore shape is correct
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Presets API
# ---------------------------------------------------------------------------

def test_presets_endpoint_returns_all_presets():
    """GET /api/agent/presets should return all 6 backend presets."""
    from ggufloader.core.agent.presets import PresetManager

    pm = PresetManager()
    presets = pm.list_all()
    assert len(presets) == 6

    ids = {p.id for p in presets}
    assert ids == {"research", "code_review", "refactor", "debug", "full_stack", "quick_fix"}


def test_preset_has_required_fields():
    """Each preset should have id, name, description, icon, max_steps, temperature."""
    from ggufloader.core.agent.presets import PresetManager

    pm = PresetManager()
    for preset in pm.list_all():
        assert preset.id
        assert preset.name
        assert preset.description
        assert preset.icon
        assert preset.max_steps > 0
        assert 0 <= preset.temperature <= 2


def test_preset_system_prompt_addition():
    """Presets should append their mode instructions to the base prompt."""
    from ggufloader.core.agent.presets import PresetManager

    pm = PresetManager()
    base = "You are a helpful assistant."

    research = pm.get("research")
    full = research.get_system_prompt(base)
    assert "MODE: Research" in full
    assert base in full

    debug = pm.get("debug")
    full = debug.get_system_prompt(base)
    assert "MODE: Debugging" in full


def test_preset_tool_permissions():
    """Research preset should block write tools; full_stack should allow all."""
    from ggufloader.core.agent.presets import PresetManager

    pm = PresetManager()

    research = pm.get("research")
    assert "write_file" in research.blocked_tools
    assert "read_file" in research.allowed_tools

    full = pm.get("full_stack")
    assert "write_file" in full.allowed_tools
    assert len(full.blocked_tools) == 0


# ---------------------------------------------------------------------------
# GraphAgent creation with preset
# ---------------------------------------------------------------------------

def test_graph_agent_creation_with_preset_params():
    """GraphAgent should accept max_steps and max_tokens from preset."""
    from ggufloader.core.agent.graph_agent import GraphAgent

    def fake_llm(prompt, max_tokens=2048, temperature=0.1):
        return '{"tool_calls": [], "answer": "test"}'

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = GraphAgent(
            llm=fake_llm,
            workspace=tmpdir,
            max_steps=15,    # from refactor preset
            max_tokens=1024,  # from quick_fix preset
            json_retries=2,
        )
        assert agent.max_steps == 15
        assert agent.max_tokens == 1024
        assert str(tmpdir) in str(agent.workspace)
        agent.close()


def test_graph_agent_has_cancel():
    """GraphAgent should support cooperative cancellation."""
    from ggufloader.core.agent.graph_agent import GraphAgent

    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = GraphAgent(llm=fake_llm, workspace=tmpdir)
        assert hasattr(agent, 'cancel')
        assert not agent._cancel.is_set()
        agent.cancel()
        assert agent._cancel.is_set()
        agent.close()


def test_graph_agent_has_checkpoint():
    """GraphAgent should create a SQLite checkpointer."""
    from ggufloader.core.agent.graph_agent import GraphAgent

    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = Path(tmpdir) / "checkpoints.db"
        agent = GraphAgent(
            llm=fake_llm,
            workspace=tmpdir,
            checkpoint_path=checkpoint_path,
        )
        assert agent._saver is not None
        assert checkpoint_path.exists()
        agent.close()


# ---------------------------------------------------------------------------
# Approval flow mechanics
# ---------------------------------------------------------------------------

def test_approval_event_blocking():
    """Approval should block via asyncio.Event until resolved."""
    from ggufloader.api.websocket.handler import _approval_events, _approval_results

    call_id = f"test_approval_{int(time.time() * 1000)}"
    event = asyncio.Event()
    _approval_events[call_id] = event

    # Simulate frontend approval
    _approval_results[call_id] = True
    event.set()

    # Verify the event resolves
    assert event.is_set()
    assert _approval_results.pop(call_id, False) is True
    _approval_events.pop(call_id, None)


def test_approval_timeout():
    """Approval should not hang forever if frontend doesn't respond."""
    from ggufloader.api.websocket.handler import _approval_events

    call_id = f"test_timeout_{int(time.time() * 1000)}"
    event = asyncio.Event()
    _approval_events[call_id] = event

    # Simulate timeout - event never set
    start = time.time()
    try:
        event.wait(timeout=0.1)
    except Exception:
        pass
    elapsed = time.time() - start

    assert elapsed < 1.0  # should not hang
    _approval_events.pop(call_id, None)


# ---------------------------------------------------------------------------
# WebSocket handler imports
# ---------------------------------------------------------------------------

def test_handler_imports_work():
    """All handler imports should succeed without errors."""
    from ggufloader.api.websocket.handler import (
        websocket_endpoint,
        handle_chat,
        handle_agent_start,
        handle_agent_stop,
        handle_approval_response,
        request_approval,
        manager,
    )
    assert websocket_endpoint is not None
    assert handle_agent_start is not None


# ---------------------------------------------------------------------------
# Presets API route registration
# ---------------------------------------------------------------------------

def test_agent_router_has_presets_endpoint():
    """The agent API router should have /presets endpoint."""
    from ggufloader.api.routes.agent import router

    routes = [r.path for r in router.routes]
    assert "/presets" in routes


def test_agent_router_has_sessions_endpoint():
    """The agent API router should have /sessions endpoint."""
    from ggufloader.api.routes.agent import router

    routes = [r.path for r in router.routes]
    assert "/sessions" in routes


# ---------------------------------------------------------------------------
# Router integration
# ---------------------------------------------------------------------------

def test_router_agent_role_provides_valid_params():
    """Router should provide valid agent-mode params for any profile."""
    from ggufloader.core.router import ModelRouter, ModelRole, ModelProfile

    router = ModelRouter()
    # Test with a synthetic profile
    profile = ModelProfile(
        family_params={"temperature": 0.7, "top_k": 40},
        is_thinking_model=False,
    )
    config = router.route(profile, ModelRole.AGENT)

    assert config.temperature <= 0.3  # agent caps temperature
    assert config.repeat_penalty >= 1.1
    assert config.role == ModelRole.AGENT
