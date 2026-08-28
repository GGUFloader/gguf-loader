"""
IntegrationTests - End-to-end agent pipeline validation.

Pattern from: SWE-agent eval harness + Aider's test suite.
Validates the complete agent workflow:
1. Config loading and validation
2. Tool registry initialization
3. Agent engine message processing
4. Tool execution and result handling
5. Memory and knowledge integration
6. Checkpoint and undo flow
7. Health monitoring
8. Audit logging
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import all agent modules
from .config_manager import ConfigManager, AgentConfig
from .tool_registry import ToolRegistry, create_default_registry
from .agent_engine import AgentEngine, extract_json
from .memory_persistence import MemoryPersistence
from .knowledge_base import KnowledgeBase
from .checkpoint_manager import CheckpointManager
from .health_monitor import HealthMonitor
from .audit_log import AuditLog, EventType
from .retry_handler import RetryHandler
from .context_budget import ContextBudget
from .presets import PresetManager
from .self_improve import SelfImprove
from .cost_estimator import CostEstimator
from .workspace_analytics import WorkspaceAnalytics


class TestResult:
    """Result of a single integration test."""

    def __init__(self, name: str, passed: bool, message: str = "",
                 duration_ms: int = 0) -> None:
        self.name = name
        self.passed = passed
        self.message = message
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "duration_ms": self.duration_ms,
        }


class IntegrationTestSuite:
    """Run integration tests for the agent pipeline.

    Usage:
        suite = IntegrationTestSuite()
        results = suite.run_all()
        for r in results:
            print(f"{'✅' if r.passed else '❌'} {r.name}: {r.message}")
    """

    def __init__(self, workspace: Path = None) -> None:
        self.workspace = workspace or Path(tempfile.mkdtemp(prefix="gguf_test_"))
        self._results: List[TestResult] = []

    def run_all(self) -> List[TestResult]:
        """Run all integration tests."""
        self._results = []
        start = time.monotonic()

        tests = [
            self.test_config_loading,
            self.test_config_validation,
            self.test_tool_registry,
            self.test_tool_execution,
            self.test_path_sandbox,
            self.test_json_extraction,
            self.test_json_repair,
            self.test_memory_persistence,
            self.test_knowledge_base,
            self.test_checkpoint_manager,
            self.test_health_monitor,
            self.test_audit_log,
            self.test_retry_handler,
            self.test_context_budget,
            self.test_presets,
            self.test_self_improve,
            self.test_cost_estimator,
            self.test_workspace_analytics,
            self.test_agent_engine_init,
        ]

        for test_fn in tests:
            test_start = time.monotonic()
            try:
                test_fn()
                duration = int((time.monotonic() - test_start) * 1000)
                # Test already added its own result
            except Exception as e:
                duration = int((time.monotonic() - test_start) * 1000)
                name = test_fn.__name__.replace("test_", "")
                self._results.append(TestResult(name, False, str(e), duration))

        total = time.monotonic() - start
        return self._results

    def _pass(self, name: str, message: str = "OK", duration_ms: int = 0) -> None:
        self._results.append(TestResult(name, True, message, duration_ms))

    def _fail(self, name: str, message: str) -> None:
        self._results.append(TestResult(name, False, message))

    # ---- Tests ----

    def test_config_loading(self) -> None:
        mgr = ConfigManager(self.workspace)
        config = mgr.load()
        assert isinstance(config, AgentConfig)
        assert config.max_steps > 0
        self._pass("config_loading")

    def test_config_validation(self) -> None:
        mgr = ConfigManager(self.workspace)
        mgr.load()
        issues = mgr.validate()
        assert isinstance(issues, list)
        self._pass("config_validation", f"{len(issues)} issues")

    def test_tool_registry(self) -> None:
        registry = create_default_registry(self.workspace)
        names = registry.names()
        assert "read_file" in names
        assert "write_file" in names
        assert "list_directory" in names
        self._pass("tool_registry", f"{len(names)} tools")

    def test_tool_execution(self) -> None:
        registry = create_default_registry(self.workspace)
        # Write a test file
        result = registry.execute("write_file", {
            "path": "test.txt",
            "content": "Hello, integration test!",
        })
        assert result["status"] == "success"

        # Read it back
        result = registry.execute("read_file", {"path": "test.txt"})
        assert result["status"] == "success"
        assert "Hello, integration test!" in result["result"]
        self._pass("tool_execution")

    def test_path_sandbox(self) -> None:
        registry = create_default_registry(self.workspace)
        # Try to escape workspace
        result = registry.execute("read_file", {"path": "../../../etc/passwd"})
        assert result["status"] == "error"
        self._pass("path_sandbox")

    def test_json_extraction(self) -> None:
        # Test from agent_engine
        text1 = '```json\n{"tool": "test", "answer": "hi"}\n```'
        data = extract_json(text1)
        assert data is not None
        assert data["answer"] == "hi"

        # Test bare JSON
        text2 = 'Here is the result: {"tool": "test"}'
        data = extract_json(text2)
        assert data is not None

        # Test no JSON
        text3 = "No JSON here"
        data = extract_json(text3)
        assert data is None

        self._pass("json_extraction")

    def test_json_repair(self) -> None:
        # Trailing comma
        text = '{"key": "value",}'
        from .agent_engine import _repair_json
        repaired = _repair_json(text)
        data = json.loads(repaired)
        assert data["key"] == "value"

        # Missing closing brace
        text2 = '{"key": "value"'
        repaired2 = _repair_json(text2)
        data2 = json.loads(repaired2)
        assert data2["key"] == "value"

        self._pass("json_repair")

    def test_memory_persistence(self) -> None:
        mem = MemoryPersistence(self.workspace)
        initial_count = mem.count()

        mem.remember("test_key", "test_value", "fact")
        assert mem.count() == initial_count + 1

        results = mem.recall("test_key")
        assert len(results) > 0
        assert results[0].value == "test_value"

        # Test persistence
        mem2 = MemoryPersistence(self.workspace)
        assert mem2.count() == mem.count()

        mem.forget("test_key")
        self._pass("memory_persistence")

    def test_knowledge_base(self) -> None:
        kb = KnowledgeBase(self.workspace)
        initial = kb.count()

        kb.store("file", "test.py", "Test file description")
        assert kb.count() == initial + 1

        results = kb.query("test")
        assert len(results) > 0

        # Test context generation
        ctx = kb.get_context_for_prompt()
        assert isinstance(ctx, str)

        self._pass("knowledge_base")

    def test_checkpoint_manager(self) -> None:
        mgr = CheckpointManager(self.workspace)

        # Create a test file
        test_file = self.workspace / "checkpoint_test.txt"
        test_file.write_text("original content")

        # Start session and backup
        mgr.start_session("test_session")
        checksum = mgr.backup("write_file", {"path": "checkpoint_test.txt"})
        assert checksum is not None

        # Modify the file
        test_file.write_text("modified content")

        # End session
        session_id = mgr.end_session()
        assert session_id is not None

        # Undo
        restored = mgr.undo_last()
        assert "checkpoint_test.txt" in restored
        assert test_file.read_text() == "original content"

        self._pass("checkpoint_manager")

    def test_health_monitor(self) -> None:
        monitor = HealthMonitor()

        monitor.record("test_metric", 42.0)
        monitor.increment("test_counter")
        monitor.gauge("test_gauge", 3.14)
        monitor.event("test", "test event")

        health = monitor.health_check()
        assert health["status"] in ("healthy", "degraded", "unhealthy")

        summary = monitor.get_summary()
        assert summary["counters"]["test_counter"] == 1
        assert summary["gauges"]["test_gauge"] == 3.14

        self._pass("health_monitor")

    def test_audit_log(self) -> None:
        log = AuditLog(self.workspace)
        log.set_session("test_session")

        log.log(EventType.TOOL_CALL, {"tool": "test"})
        log.log(EventType.TOOL_RESULT, {"tool": "test", "status": "success"})
        log.log(EventType.LLM_REQUEST, {"tokens": 100})

        entries = log.query(event_type=EventType.TOOL_CALL)
        assert len(entries) >= 1

        summary = log.get_session_summary()
        assert summary["total_events"] >= 3

        self._pass("audit_log")

    def test_retry_handler(self) -> None:
        handler = RetryHandler()

        # Test successful call
        result = handler.retry_llm(lambda: "success")
        assert result == "success"

        # Test stats
        stats = handler.get_stats()
        assert "total_retries" in stats

        self._pass("retry_handler")

    def test_context_budget(self) -> None:
        budget = ContextBudget(total_budget=4000, system_prompt_tokens=200)

        # Build a small history
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        strategy = budget.check_budget(history)
        assert strategy == "ok"

        # Test compaction
        budget.compact(history)
        stats = budget.get_stats()
        assert stats["total_budget"] == 4000

        self._pass("context_budget")

    def test_presets(self) -> None:
        pm = PresetManager()

        presets = pm.list_all()
        assert len(presets) >= 6

        debug = pm.get("debug")
        assert debug is not None
        assert debug.icon == "🐛"

        summary = pm.get_summary()
        assert len(summary) >= 6

        self._pass("presets")

    def test_self_improve(self) -> None:
        si = SelfImprove(self.workspace)

        si.record_correction(
            context="Python editing",
            agent_action="Used os.path",
            correct_action="Used pathlib",
            category="style",
        )

        advice = si.get_advice("Python editing")
        assert "pathlib" in advice or "os.path" in advice

        stats = si.get_stats()
        assert stats["corrections"] >= 1

        self._pass("self_improve")

    def test_cost_estimator(self) -> None:
        ce = CostEstimator()
        ce.start_session("test-model")
        ce.record_call(input_tokens=500, output_tokens=200, generation_ms=1000)

        summary = ce.summary()
        assert summary["total_calls"] == 1
        assert summary["input_tokens"] == 500

        throughput = ce.get_throughput()
        assert throughput["tokens_per_second"] > 0

        self._pass("cost_estimator")

    def test_workspace_analytics(self) -> None:
        analytics = WorkspaceAnalytics(self.workspace)
        report = analytics.generate_report()

        assert "metrics" in report
        assert "health" in report
        assert "insights" in report

        summary = analytics.get_language_summary()
        assert isinstance(summary, str)

        self._pass("workspace_analytics")

    def test_agent_engine_init(self) -> None:
        # Minimal LLM mock
        def mock_llm(prompt, **kwargs):
            return '{"tool_calls": [], "answer": "Test response"}'

        engine = AgentEngine(
            llm=mock_llm,
            workspace=self.workspace,
            max_steps=2,
        )

        # Verify all subsystems are initialized
        assert engine._retry_handler is not None
        assert engine._checkpoint_mgr is not None
        assert engine._context_budget is not None
        assert engine._memory_store is not None
        assert engine._knowledge is not None
        assert engine._health is not None
        assert engine._audit is not None
        assert engine._self_improve is not None

        self._pass("agent_engine_init")

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all test results."""
        total = len(self._results)
        passed = sum(1 for r in self._results if r.passed)
        failed = total - passed
        total_ms = sum(r.duration_ms for r in self._results)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1) if total else 0,
            "total_duration_ms": total_ms,
            "results": [r.to_dict() for r in self._results],
        }
