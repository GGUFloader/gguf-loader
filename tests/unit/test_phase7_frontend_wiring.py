"""Tests for Phase 7: SSE streaming, workspace dashboard, session replay panel API."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# SSE streaming endpoint
# ---------------------------------------------------------------------------

class TestSSEStreamEndpoint:
    """Tests for POST /api/chat/stream."""

    def test_stream_imports(self):
        """chat module should import without errors."""
        from ggufloader.api.routes.chat import stream_message, workspace_dashboard

    def test_stream_requires_model(self):
        """stream_message should raise if no model loaded."""
        from ggufloader.api.routes.chat import ChatRequest, stream_message

        req = ChatRequest(message="hello")
        # When backend is None, should raise HTTPException
        with patch("ggufloader.api.routes.chat.get_model_backend", return_value=None):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(
                    stream_message(req)
                )
            assert exc_info.value.status_code == 400

    def test_stream_returns_sse_when_model_loaded(self):
        """stream_message should return a StreamingResponse."""
        from ggufloader.api.routes.chat import ChatRequest, stream_message

        mock_backend = MagicMock()
        mock_backend.chat_stream.return_value = iter(["Hello", " world"])

        req = ChatRequest(message="hello", temperature=0.5)
        with patch("ggufloader.api.routes.chat.get_model_backend", return_value=mock_backend):
            from fastapi.responses import StreamingResponse
            result = asyncio.get_event_loop().run_until_complete(stream_message(req))
            assert isinstance(result, StreamingResponse)

    def test_stream_non_streaming_fallback(self):
        """stream_message should work when backend has no chat_stream."""
        from ggufloader.api.routes.chat import ChatRequest, stream_message

        mock_backend = MagicMock(spec=["chat"])  # no chat_stream
        mock_backend.chat.return_value = "Fallback response"

        req = ChatRequest(message="hello")
        with patch("ggufloader.api.routes.chat.get_model_backend", return_value=mock_backend):
            from fastapi.responses import StreamingResponse
            result = asyncio.get_event_loop().run_until_complete(stream_message(req))
            assert isinstance(result, StreamingResponse)


# ---------------------------------------------------------------------------
# Workspace dashboard endpoint
# ---------------------------------------------------------------------------

class TestWorkspaceDashboard:
    """Tests for GET /api/chat/dashboard."""

    def test_dashboard_imports(self):
        from ggufloader.api.routes.chat import workspace_dashboard

    def test_dashboard_returns_dict(self):
        from ggufloader.api.routes.chat import workspace_dashboard

        result = asyncio.get_event_loop().run_until_complete(workspace_dashboard())
        assert isinstance(result, dict)
        assert "workspace" in result
        assert "plugins" in result
        assert "memory" in result
        assert "sessions" in result
        assert "model" in result
        assert "ram_gb" in result

    def test_dashboard_plugins_list(self):
        from ggufloader.api.routes.chat import workspace_dashboard

        result = asyncio.get_event_loop().run_until_complete(workspace_dashboard())
        assert isinstance(result["plugins"], list)

    def test_dashboard_memory_structure(self):
        from ggufloader.api.routes.chat import workspace_dashboard

        result = asyncio.get_event_loop().run_until_complete(workspace_dashboard())
        mem = result["memory"]
        assert "entries" in mem
        assert "count" in mem
        assert isinstance(mem["entries"], list)
        assert isinstance(mem["count"], int)


# ---------------------------------------------------------------------------
# Agent sessions/replays/exports endpoints
# ---------------------------------------------------------------------------

class TestAgentSessionEndpoints:
    """Tests for the new agent session list endpoints."""

    def test_replays_imports(self):
        from ggufloader.api.routes.agent import list_replays, list_exports, agent_health

    def test_replays_returns_list(self):
        from ggufloader.api.routes.agent import list_replays
        result = asyncio.get_event_loop().run_until_complete(list_replays())
        assert isinstance(result, list)

    def test_exports_returns_list(self):
        from ggufloader.api.routes.agent import list_exports
        result = asyncio.get_event_loop().run_until_complete(list_exports())
        assert isinstance(result, list)

    def test_health_endpoint(self):
        from ggufloader.api.routes.agent import agent_health
        result = asyncio.get_event_loop().run_until_complete(agent_health())
        assert "health" in result
        assert "cost" in result
        assert "rate_limiter" in result
        assert "agent_running" in result


# ---------------------------------------------------------------------------
# Session replay comparison (bugfix verification)
# ---------------------------------------------------------------------------

class TestSessionReplayComparison:
    """Verify the compare_sessions divergence bugfix."""

    def test_identical_sessions_have_full_prefix(self):
        """When all actions match, identical_prefix should equal total steps."""
        from ggufloader.core.agent.session_replay import SessionReplay

        with tempfile.TemporaryDirectory() as tmp:
            replay = SessionReplay(Path(tmp))
            a = replay.create_session("a")
            replay.record_user_message("msg1")
            replay.record_agent_response("resp1")
            replay.record_tool_call("read_file", {"path": "foo.py"})
            replay.save_session(a)

            b = replay.create_session("b")
            replay.record_user_message("msg1")
            replay.record_agent_response("resp1")
            replay.record_tool_call("read_file", {"path": "foo.py"})
            replay.save_session(b)

            comparison = replay.compare_sessions(a, b)
            assert comparison["identical_prefix"] == 3  # all 3 match
            assert comparison["divergence_point"] == 3

    def test_diverging_sessions(self):
        """When actions diverge, divergence should point to the mismatch."""
        from ggufloader.core.agent.session_replay import SessionReplay

        with tempfile.TemporaryDirectory() as tmp:
            replay = SessionReplay(Path(tmp))
            a = replay.create_session("a")
            replay.record_user_message("msg1")
            replay.record_agent_response("resp1")
            replay.record_tool_call("read_file", {"path": "a.py"})
            replay.record_tool_result("read_file", "success", result="content")
            replay.save_session(a)

            b = replay.create_session("b")
            replay.record_user_message("msg1")
            replay.record_agent_response("resp1")
            replay.record_tool_call("read_file", {"path": "b.py"})
            replay.record_user_message("different")  # different action type
            replay.save_session(b)

            comparison = replay.compare_sessions(a, b)
            assert comparison["identical_prefix"] == 3  # first 3 match (user, agent, tool_call)
            assert comparison["divergence_point"] == 3
