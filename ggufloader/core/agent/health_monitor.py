"""
HealthMonitor - System diagnostics and agent health tracking.

Pattern from: OpenHands runtime metrics + DeepSeek StatsLine.
Provides real-time monitoring of:
- System resources (CPU, memory, disk)
- Agent performance (steps, tokens, timing)
- Model status (loaded, context usage)
- Tool execution health (success rate, latency)
- Error rates and patterns

The health monitor is the central observability hub that all
other modules report to.
"""

from __future__ import annotations

import logging
import os
import platform
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Rolling window size for metrics
METRICS_WINDOW = 100


class HealthStatus:
    """Overall health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class MetricPoint:
    """A single metric data point."""

    def __init__(self, name: str, value: float, timestamp: float = None,
                 tags: Dict[str, str] = None) -> None:
        self.name = name
        self.value = value
        self.timestamp = timestamp or time.time()
        self.tags = tags or {}


class HealthMonitor:
    """Central health monitoring for the agent system.

    Usage:
        monitor = HealthMonitor()

        # Record metrics
        monitor.record("llm.latency_ms", 500)
        monitor.record("tool.success", 1)
        monitor.record("tool.failure", 0)

        # Get health check
        health = monitor.health_check()
        print(health["status"])  # "healthy"
    """

    def __init__(self) -> None:
        self._metrics: Dict[str, deque] = {}
        self._events: deque = deque(maxlen=500)
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._alerts: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Alert thresholds
        self._thresholds = {
            "cpu_percent": 90.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "error_rate": 0.3,  # 30% error rate
            "llm_latency_ms": 30000,  # 30s
        }

    def record(self, name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Record a metric data point."""
        point = MetricPoint(name, value, tags=tags)
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = deque(maxlen=METRICS_WINDOW)
            self._metrics[name].append(point)

        # Check thresholds
        self._check_threshold(name, value)

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment a counter."""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def gauge(self, name: str, value: float) -> None:
        """Set a gauge value (latest value wins)."""
        with self._lock:
            self._gauges[name] = value

    def event(self, category: str, message: str, level: str = "info") -> None:
        """Record a discrete event."""
        event = {
            "category": category,
            "message": message,
            "level": level,
            "timestamp": time.time(),
        }
        with self._lock:
            self._events.append(event)

    def _check_threshold(self, name: str, value: float) -> None:
        """Check if a metric exceeds its threshold."""
        threshold = self._thresholds.get(name)
        if threshold and value > threshold:
            alert = {
                "metric": name,
                "value": value,
                "threshold": threshold,
                "timestamp": time.time(),
                "level": "warning" if value < threshold * 1.2 else "critical",
            }
            self._alerts.append(alert)
            if len(self._alerts) > 100:
                self._alerts = self._alerts[-100:]
            logger.warning("Health alert: %s = %.1f (threshold: %.1f)",
                          name, value, threshold)

    def health_check(self) -> Dict[str, Any]:
        """Perform a comprehensive health check."""
        status = HealthStatus.HEALTHY
        issues = []

        # System metrics
        sys_metrics = self._get_system_metrics()

        # Check CPU
        if sys_metrics.get("cpu_percent", 0) > self._thresholds["cpu_percent"]:
            status = HealthStatus.DEGRADED
            issues.append(f"High CPU: {sys_metrics['cpu_percent']:.1f}%")

        # Check memory
        if sys_metrics.get("memory_percent", 0) > self._thresholds["memory_percent"]:
            status = HealthStatus.DEGRADED
            issues.append(f"High memory: {sys_metrics['memory_percent']:.1f}%")

        # Check error rate
        errors = self._counters.get("errors", 0)
        total = self._counters.get("total_operations", 0)
        if total > 10:
            error_rate = errors / total
            if error_rate > self._thresholds["error_rate"]:
                status = HealthStatus.UNHEALTHY
                issues.append(f"High error rate: {error_rate:.1%}")

        # Check uptime
        uptime = time.time() - self._start_time

        return {
            "status": status,
            "uptime_seconds": round(uptime, 1),
            "system": sys_metrics,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "recent_alerts": self._alerts[-5:],
            "issues": issues,
        }

    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get current system resource metrics."""
        metrics = {
            "platform": platform.system(),
            "python": platform.python_version(),
        }

        try:
            # CPU usage (non-blocking estimate)
            metrics["cpu_count"] = os.cpu_count() or 0

            # Memory
            try:
                import psutil
                mem = psutil.virtual_memory()
                metrics["memory_percent"] = mem.percent
                metrics["memory_used_gb"] = round(mem.used / (1024**3), 2)
                metrics["memory_total_gb"] = round(mem.total / (1024**3), 2)

                disk = psutil.disk_usage("/")
                metrics["disk_percent"] = disk.percent
                metrics["disk_free_gb"] = round(disk.free / (1024**3), 2)
            except ImportError:
                # Fallback without psutil
                metrics["memory_percent"] = 0
                metrics["disk_percent"] = 0

        except Exception:
            pass

        return metrics

    def get_metric_history(self, name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent values for a metric."""
        with self._lock:
            points = list(self._metrics.get(name, []))
        return [
            {"value": p.value, "timestamp": p.timestamp, "tags": p.tags}
            for p in points[-limit:]
        ]

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> Optional[float]:
        return self._gauges.get(name)

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events)[-limit:]

    def get_alerts(self, level: str = None) -> List[Dict[str, Any]]:
        if level:
            return [a for a in self._alerts if a.get("level") == level]
        return list(self._alerts)

    def get_summary(self) -> Dict[str, Any]:
        """Get a compact summary of all metrics."""
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
        return {
            "uptime": round(time.time() - self._start_time, 1),
            "counters": counters,
            "gauges": gauges,
            "alerts": len(self._alerts),
            "events": len(self._events),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()
            self._events.clear()
            self._counters.clear()
            self._gauges.clear()
            self._alerts.clear()
            self._start_time = time.time()
