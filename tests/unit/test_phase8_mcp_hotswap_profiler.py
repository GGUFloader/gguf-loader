"""Tests for Phase 8: MCP Bridge, Model Hot-Swap, and Agent Profiler."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# MCPBridge
# ---------------------------------------------------------------------------

class TestMCPBridge:
    """Tests for the MCP tool bridge."""

    def test_import(self):
        from ggufloader.core.agent.mcp_bridge import MCPBridge, MCPTool, MCPServerProcess

    def test_add_remove_server(self):
        from ggufloader.core.agent.mcp_bridge import MCPBridge

        with tempfile.TemporaryDirectory() as tmp:
            bridge = MCPBridge(Path(tmp))
            bridge.add_server("test", "echo", ["hello"])
            assert len(bridge._servers) == 1
            bridge.remove_server("test")
            assert len(bridge._servers) == 0

    def test_get_status_disconnected(self):
        from ggufloader.core.agent.mcp_bridge import MCPBridge

        with tempfile.TemporaryDirectory() as tmp:
            bridge = MCPBridge(Path(tmp))
            bridge.add_server("test", "echo", ["hello"])
            statuses = bridge.get_status()
            assert len(statuses) == 1
            assert statuses[0]["name"] == "test"
            assert statuses[0]["connected"] is False

    def test_get_all_tools_empty(self):
        from ggufloader.core.agent.mcp_bridge import MCPBridge

        with tempfile.TemporaryDirectory() as tmp:
            bridge = MCPBridge(Path(tmp))
            tools = bridge.get_all_tools()
            assert tools == []

    def test_call_tool_server_not_found(self):
        from ggufloader.core.agent.mcp_bridge import MCPBridge

        with tempfile.TemporaryDirectory() as tmp:
            bridge = MCPBridge(Path(tmp))
            result = bridge.call_tool("nonexistent", "tool", {})
            assert result["status"] == "error"
            assert "not found" in result["error"]

    def test_register_tools_with_empty_servers(self):
        from ggufloader.core.agent.mcp_bridge import MCPBridge
        from ggufloader.core.agent.tool_registry import ToolRegistry

        with tempfile.TemporaryDirectory() as tmp:
            bridge = MCPBridge(Path(tmp))
            registry = ToolRegistry(Path(tmp))
            count = bridge.register_tools(registry)
            assert count == 0

    def test_mcp_tool_wrapper(self):
        from ggufloader.core.agent.mcp_bridge import MCPTool, MCPBridge

        with tempfile.TemporaryDirectory() as tmp:
            bridge = MCPBridge(Path(tmp))
            tool_def = {
                "name": "test_tool",
                "description": "A test tool",
                "inputSchema": {"type": "object", "properties": {"x": {"type": "string"}}},
            }
            tool = MCPTool(Path(tmp), "myserver", tool_def, bridge)
            assert tool.name == "test_tool"
            assert tool.description == "A test tool"
            assert tool.requires_approval({}) is False
            # Register the server as disconnected
            bridge.add_server("myserver", "echo", [])
            result = tool.execute({"x": "hello"})
            assert result["status"] == "error"

    def test_connect_all_returns_dict(self):
        from ggufloader.core.agent.mcp_bridge import MCPBridge

        with tempfile.TemporaryDirectory() as tmp:
            bridge = MCPBridge(Path(tmp))
            # Add a server that will fail to connect (fake command)
            bridge.add_server("bad", "nonexistent_command_xyz", [])
            results = bridge.connect_all(timeout=1.0)
            assert "bad" in results
            assert results["bad"] is False


# ---------------------------------------------------------------------------
# ModelHotSwap
# ---------------------------------------------------------------------------

class TestModelHotSwap:
    """Tests for the model hot-swap module."""

    def test_import(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap, ModelInfo

    def test_model_info_to_dict(self):
        from ggufloader.core.agent.model_hotswap import ModelInfo

        info = ModelInfo(
            path="/models/test.gguf",
            name="test-model",
            family="llama",
            architecture="llama",
            size_gb=4.0,
            context_length=8192,
        )
        d = info.to_dict()
        assert d["path"] == "/models/test.gguf"
        assert d["name"] == "test-model"
        assert d["family"] == "llama"
        assert d["context_length"] == 8192

    def test_switch_to_success(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap

        mock_backend = MagicMock()
        load_fn = MagicMock(return_value=mock_backend)
        unload_fn = MagicMock()

        swap = ModelHotSwap(load_fn=load_fn, unload_fn=unload_fn)
        result = swap.switch_to("/models/test.gguf", n_ctx=4096)

        assert result["status"] == "success"
        assert result["model"]["path"] == "/models/test.gguf"
        assert swap.is_loaded
        assert swap.backend is mock_backend
        load_fn.assert_called_once()

    def test_switch_to_same_model_no_change(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap

        mock_backend = MagicMock()
        load_fn = MagicMock(return_value=mock_backend)
        unload_fn = MagicMock()

        swap = ModelHotSwap(load_fn=load_fn, unload_fn=unload_fn)
        swap.switch_to("/models/test.gguf")
        load_fn.reset_mock()

        result = swap.switch_to("/models/test.gguf")
        assert result["status"] == "no_change"
        load_fn.assert_not_called()

    def test_switch_unloads_previous(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap

        load_fn = MagicMock(return_value="backend_a")
        unload_fn = MagicMock()

        swap = ModelHotSwap(load_fn=load_fn, unload_fn=unload_fn)
        swap.switch_to("/models/a.gguf")
        assert unload_fn.call_count == 0  # no previous to unload

        load_fn.return_value = "backend_b"
        swap.switch_to("/models/b.gguf")
        assert unload_fn.call_count == 1  # unloaded model A

    def test_switch_failure_triggers_fallback(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap

        call_count = [0]

        def selective_load(path, **kwargs):
            call_count[0] += 1
            if "primary" in path:
                raise RuntimeError("Primary model failed")
            return f"fallback_backend_{call_count[0]}"

        unload_fn = MagicMock()
        swap = ModelHotSwap(load_fn=selective_load, unload_fn=unload_fn)
        swap.set_fallback_chain(["/models/primary.gguf", "/models/fallback.gguf"])

        result = swap.switch_to("/models/primary.gguf")
        assert result["status"] == "success"
        assert "fallback" in result.get("message", "").lower()

    def test_switch_all_fallbacks_fail(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap

        def fail_load(path, **kwargs):
            raise RuntimeError("All models failed")

        unload_fn = MagicMock()
        swap = ModelHotSwap(load_fn=fail_load, unload_fn=unload_fn)
        swap.set_fallback_chain(["/models/a.gguf", "/models/b.gguf"])

        result = swap.switch_to("/models/a.gguf")
        assert result["status"] == "error"
        assert not swap.is_loaded

    def test_unload(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap

        load_fn = MagicMock(return_value="backend")
        unload_fn = MagicMock()

        swap = ModelHotSwap(load_fn=load_fn, unload_fn=unload_fn)
        swap.switch_to("/models/test.gguf")
        assert swap.is_loaded

        result = swap.unload()
        assert result["status"] == "unloaded"
        assert not swap.is_loaded
        unload_fn.assert_called_once()

    def test_unload_when_no_model(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap

        swap = ModelHotSwap(load_fn=MagicMock(), unload_fn=MagicMock())
        result = swap.unload()
        assert result["status"] == "no_model"

    def test_status(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap

        swap = ModelHotSwap(load_fn=MagicMock(return_value="b"), unload_fn=MagicMock())
        status = swap.status()
        assert status["loaded"] is False
        assert status["active_model"] is None
        assert status["fallback_chain"] == []

        swap.switch_to("/models/test.gguf")
        status = swap.status()
        assert status["loaded"] is True
        assert status["active_model"]["path"] == "/models/test.gguf"

    def test_switch_history(self):
        from ggufloader.core.agent.model_hotswap import ModelHotSwap

        load_fn = MagicMock(return_value="backend")
        unload_fn = MagicMock()
        swap = ModelHotSwap(load_fn=load_fn, unload_fn=unload_fn)

        swap.switch_to("/models/a.gguf")
        swap.switch_to("/models/b.gguf")
        swap.unload()

        history = swap.get_history()
        assert len(history) == 3
        assert history[0]["action"] == "switch"
        assert history[1]["action"] == "switch"
        assert history[2]["action"] == "unload"


# ---------------------------------------------------------------------------
# AgentProfiler
# ---------------------------------------------------------------------------

class TestAgentProfiler:
    """Tests for the performance profiler."""

    def test_import(self):
        from ggufloader.core.agent.profiler import AgentProfiler, StepProfile, RunProfile

    def test_basic_run(self):
        from ggufloader.core.agent.profiler import AgentProfiler

        profiler = AgentProfiler()
        profiler.start_run("test_run")

        profiler.begin_step("llm_call")
        time.sleep(0.01)
        profiler.end_step(input_tokens=100, output_tokens=50)

        profiler.begin_step("tool_execute", tool_name="read_file")
        time.sleep(0.01)
        profiler.end_step(success=True)

        summary = profiler.finish_run()
        assert summary["run_id"] == "test_run"
        assert summary["step_count"] == 2
        assert summary["total_input_tokens"] == 100
        assert summary["total_output_tokens"] == 50
        assert summary["llm_time_ms"] > 0
        assert summary["tool_time_ms"] > 0

    def test_bottleneck_detection(self):
        from ggufloader.core.agent.profiler import AgentProfiler

        profiler = AgentProfiler()
        profiler.start_run("test")

        # Fast LLM call
        profiler.begin_step("llm_call")
        profiler.end_step(input_tokens=100, output_tokens=50)

        # Slow tool call
        profiler.begin_step("tool_execute", tool_name="run_command")
        time.sleep(0.05)
        profiler.end_step(success=True)

        summary = profiler.finish_run()
        bottleneck = summary["bottleneck"]
        assert bottleneck is not None
        assert bottleneck["tool_name"] == "run_command"

    def test_tool_success_rate(self):
        from ggufloader.core.agent.profiler import AgentProfiler

        profiler = AgentProfiler()
        profiler.start_run("test")

        profiler.begin_step("tool_execute", tool_name="read_file")
        profiler.end_step(success=True)

        profiler.begin_step("tool_execute", tool_name="write_file")
        profiler.end_step(success=False, error="permission denied")

        profiler.begin_step("tool_execute", tool_name="edit_file")
        profiler.end_step(success=True)

        summary = profiler.finish_run()
        assert abs(summary["tool_success_rate"] - 2 / 3) < 0.01

    def test_tokens_per_second(self):
        from ggufloader.core.agent.profiler import AgentProfiler

        profiler = AgentProfiler()
        profiler.start_run("test")

        profiler.begin_step("llm_call")
        time.sleep(0.02)
        profiler.end_step(input_tokens=500, output_tokens=200)

        summary = profiler.finish_run()
        assert summary["tokens_per_second"] > 0

    def test_history(self):
        from ggufloader.core.agent.profiler import AgentProfiler

        profiler = AgentProfiler()
        for i in range(3):
            profiler.start_run(f"run_{i}")
            profiler.begin_step("llm_call")
            profiler.end_step(input_tokens=100, output_tokens=50)
            profiler.finish_run()

        history = profiler.get_history()
        assert len(history) == 3
        assert history[2]["run_id"] == "run_2"

    def test_step_breakdown(self):
        from ggufloader.core.agent.profiler import AgentProfiler

        profiler = AgentProfiler()
        profiler.start_run("detailed")
        profiler.begin_step("llm_call")
        profiler.end_step(input_tokens=200, output_tokens=100)
        profiler.begin_step("tool_execute", tool_name="glob")
        profiler.end_step(success=True)
        profiler.finish_run()

        breakdown = profiler.get_step_breakdown(limit=1)
        assert len(breakdown) == 1
        assert len(breakdown[0]["steps"]) == 2
        assert breakdown[0]["steps"][0]["action"] == "llm_call"
        assert breakdown[0]["steps"][1]["tool_name"] == "glob"

    def test_analyze_bottlenecks_empty(self):
        from ggufloader.core.agent.profiler import AgentProfiler

        profiler = AgentProfiler()
        analysis = profiler.analyze_bottlenecks()
        assert analysis["bottlenecks"] == []
        assert analysis["suggestions"] == []

    def test_throughput_history(self):
        from ggufloader.core.agent.profiler import AgentProfiler

        profiler = AgentProfiler()
        profiler.start_run("throughput_test")
        profiler.begin_step("llm_call")
        time.sleep(0.01)
        profiler.end_step(input_tokens=500, output_tokens=200)
        profiler.finish_run()

        tp = profiler.get_throughput_history()
        assert len(tp) == 1
        assert tp[0]["tps"] > 0

    def test_run_profile_properties(self):
        from ggufloader.core.agent.profiler import RunProfile, StepProfile

        run = RunProfile(run_id="test", start_time=0, end_time=10)
        run.steps = [
            StepProfile(index=0, action="llm_call", start_time=0, end_time=3, duration_ms=3000),
            StepProfile(index=1, action="tool_execute", start_time=3, end_time=5, duration_ms=2000),
            StepProfile(index=2, action="approval_wait", start_time=5, end_time=8, duration_ms=3000),
            StepProfile(index=3, action="llm_call", start_time=8, end_time=10, duration_ms=2000),
        ]
        run.total_input_tokens = 1000
        run.total_output_tokens = 500

        assert run.total_duration_ms == 10000
        assert run.llm_time_ms == 5000
        assert run.tool_time_ms == 2000
        assert run.approval_time_ms == 3000
        assert run.total_tokens == 1500

    def test_begin_step_without_run_is_noop(self):
        from ggufloader.core.agent.profiler import AgentProfiler

        profiler = AgentProfiler()
        # Should not raise
        profiler.begin_step("llm_call")
        profiler.end_step(input_tokens=100, output_tokens=50)
        # No crash, no state change
        assert profiler._current_run is None
