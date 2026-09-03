"""Tests for phase 5: audit log, cost estimator, health monitor, rate limiter."""

import tempfile
import time
from pathlib import Path

import pytest

from ggufloader.core.agent.audit_log import AuditLog, EventType
from ggufloader.core.agent.cost_estimator import CostEstimator
from ggufloader.core.agent.health_monitor import HealthMonitor, HealthStatus
from ggufloader.core.agent.rate_limiter import RateLimiter, TokenBucket
from ggufloader.core.agent.graph_agent import GraphAgent


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

def test_audit_log_records_events():
    """AuditLog should record events and query them."""
    log = AuditLog()
    log.log(EventType.TOOL_CALL, {"tool": "read_file", "path": "foo.py"})
    log.log(EventType.TOOL_RESULT, {"tool": "read_file", "status": "success"})

    entries = log.query(event_type=EventType.TOOL_CALL)
    assert len(entries) == 1
    assert entries[0].data["tool"] == "read_file"


def test_audit_log_tool_stats():
    """get_tool_stats should aggregate by tool."""
    log = AuditLog()
    log.log_tool_result("read_file", "success")
    log.log_tool_result("read_file", "success")
    log.log_tool_result("write_file", "error")

    stats = log.get_tool_stats()
    assert stats["total_results"] == 3
    assert stats["by_tool"]["read_file"]["success"] == 2
    assert stats["by_tool"]["write_file"]["error"] == 1


def test_audit_log_session_summary():
    """Session summary should report correct counts."""
    log = AuditLog()
    log.set_session("test-session")
    log.log(EventType.TOOL_CALL, {"tool": "list"})
    log.log(EventType.ERROR, {"error": "timeout"})

    summary = log.get_session_summary()
    assert summary["session_id"] == "test-session"
    assert summary["errors"] == 1


def test_audit_log_persistence(tmp_path):
    """Audit log should export/import JSON."""
    log = AuditLog(tmp_path)
    log.log(EventType.INFO, {"message": "test"})
    log.export_json("audit.json")

    log2 = AuditLog(tmp_path)
    count = log2.load_from_json("audit.json")
    assert count == 1


def test_audit_log_trim_old():
    """Old entries should be trimmed when exceeding max."""
    log = AuditLog()
    log._max_entries = 10
    for i in range(15):
        log.log(EventType.INFO, {"i": i})
    assert len(log._entries) == 10


# ---------------------------------------------------------------------------
# CostEstimator
# ---------------------------------------------------------------------------

def test_cost_estimator_record_and_summary():
    """CostEstimator should track tokens and produce a summary."""
    cost = CostEstimator()
    cost.start_session("mistral-7b", gpu_name="rtx_4090")

    cost.record_call(input_tokens=500, output_tokens=200, generation_ms=1000)
    cost.record_call(input_tokens=300, output_tokens=100, generation_ms=500)

    summary = cost.summary()
    assert summary["total_calls"] == 2
    assert summary["input_tokens"] == 800
    assert summary["output_tokens"] == 300
    assert summary["total_generation_ms"] == 1500


def test_cost_estimator_throughput():
    """Throughput should be calculated correctly."""
    cost = CostEstimator()
    cost.start_session("test")
    cost.record_call(input_tokens=1000, output_tokens=1000, generation_ms=2000)

    tp = cost.get_throughput()
    assert tp["tokens_per_second"] > 0
    assert tp["ms_per_token"] > 0


def test_cost_estimator_electricity():
    """Electricity cost should be a small positive number."""
    cost = CostEstimator()
    cost.start_session("test", gpu_name="rtx_4090")
    cost.record_call(input_tokens=10000, output_tokens=5000, generation_ms=10000)

    elec = cost.estimate_electricity_cost()
    assert elec > 0
    assert elec < 1.0  # should be very small for local inference


def test_cost_estimator_api_comparison():
    """API cost comparison should return pricing for known models."""
    cost = CostEstimator()
    cost.start_session("gpt-4o")
    cost.record_call(input_tokens=1000, output_tokens=500)

    api = cost.estimate_api_cost("gpt-4o")
    assert api is not None
    assert api["total"] > 0


# ---------------------------------------------------------------------------
# HealthMonitor
# ---------------------------------------------------------------------------

def test_health_monitor_records_metrics():
    """HealthMonitor should record and retrieve metrics."""
    monitor = HealthMonitor()
    monitor.record("llm.latency_ms", 500)
    monitor.record("llm.latency_ms", 300)

    history = monitor.get_metric_history("llm.latency_ms")
    assert len(history) == 2
    assert history[0]["value"] == 500


def test_health_monitor_counters():
    """Counters should increment correctly."""
    monitor = HealthMonitor()
    monitor.increment("tool_calls")
    monitor.increment("tool_calls")
    monitor.increment("errors")

    assert monitor.get_counter("tool_calls") == 2
    assert monitor.get_counter("errors") == 1


def test_health_monitor_health_check():
    """Health check should return a valid status."""
    monitor = HealthMonitor()
    health = monitor.health_check()
    assert health["status"] in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
    assert "uptime_seconds" in health


def test_health_monitor_alerts():
    """Exceeding thresholds should generate alerts."""
    monitor = HealthMonitor()
    monitor._thresholds["test_metric"] = 10.0
    monitor.record("test_metric", 15.0)  # exceeds threshold

    alerts = monitor.get_alerts()
    assert len(alerts) >= 1
    assert alerts[0]["metric"] == "test_metric"


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

def test_rate_limiter_allows_normal():
    """Normal usage should be allowed."""
    limiter = RateLimiter(llm_rpm=30, tool_rpm=100)
    assert limiter.allow_llm() is True
    assert limiter.allow_tool() is True


def test_rate_limiter_token_bucket():
    """TokenBucket should refill over time."""
    bucket = TokenBucket(capacity=5, refill_rate=10.0)  # 10/sec
    for _ in range(5):
        assert bucket.consume() is True
    assert bucket.consume() is False  # empty

    time.sleep(0.2)  # refill ~2 tokens
    assert bucket.consume() is True


def test_rate_limiter_stats():
    """Stats should track requests and rejections."""
    limiter = RateLimiter(llm_rpm=1, burst=1)
    limiter.allow_llm()  # first should pass
    limiter.allow_llm()  # second should be rejected (burst=1)

    stats = limiter.get_stats()
    assert stats["llm_requests"] == 2
    assert stats["llm_rejected"] == 1


# ---------------------------------------------------------------------------
# GraphAgent wiring
# ---------------------------------------------------------------------------

def test_graph_agent_has_lightweight_core(tmp_path):
    """GraphAgent should have lightweight core attributes."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "ok"}'

    agent = GraphAgent(llm=fake_llm, workspace=tmp_path, system_prompt='You are a test assistant for unit tests.')
    assert hasattr(agent, '_context_budget')
    assert hasattr(agent, '_prefix_cache')
    assert hasattr(agent, '_workspace_ctx')
    agent.close()


def test_graph_agent_processes_lightweight(tmp_path):
    """GraphAgent should process messages in lightweight mode."""
    def fake_llm(prompt, **kwargs):
        return '{"tool_calls": [], "answer": "Hello!"}'

    agent = GraphAgent(llm=fake_llm, workspace=tmp_path, max_steps=2, system_prompt='You are a test assistant for unit tests.')
    result = agent.process(user_message="Hi")

    assert result["response"] == "Hello!"
    agent.close()


def test_agent_health_endpoint():
    """GET /api/agent/health should return valid data."""
    from ggufloader.api.routes.agent import agent_health
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(agent_health())
    assert "health" in result
    assert "cost" in result
    assert "rate_limiter" in result
