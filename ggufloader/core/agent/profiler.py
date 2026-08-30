"""
AgentProfiler - Performance profiling for agent runs.

Tracks:
- Per-step latency (LLM calls, tool execution, approval waits)
- Token throughput over time (rolling window)
- Memory usage snapshots
- Bottleneck detection (slowest steps, longest waits)
- Timeline visualization data

Pattern from: LangSmith tracing + OpenHands runtime metrics.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StepProfile:
    """Profile data for a single agent step."""
    index: int
    action: str  # "llm_call", "tool_execute", "approval_wait", "planning", "final_answer"
    tool_name: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "action": self.action,
            "tool_name": self.tool_name,
            "duration_ms": round(self.duration_ms, 1),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens_per_second": round(
                self.output_tokens / (self.duration_ms / 1000), 1
            ) if self.duration_ms > 0 and self.output_tokens > 0 else 0,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class RunProfile:
    """Complete profile for one agent run (one user message → final answer)."""
    run_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    steps: List[StepProfile] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    peak_memory_mb: float = 0.0

    @property
    def total_duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def llm_time_ms(self) -> float:
        return sum(s.duration_ms for s in self.steps if s.action == "llm_call")

    @property
    def tool_time_ms(self) -> float:
        return sum(s.duration_ms for s in self.steps if s.action == "tool_execute")

    @property
    def approval_time_ms(self) -> float:
        return sum(s.duration_ms for s in self.steps if s.action == "approval_wait")

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def tokens_per_second(self) -> float:
        if self.llm_time_ms <= 0:
            return 0.0
        return round(self.total_output_tokens / (self.llm_time_ms / 1000), 1)

    @property
    def tool_success_rate(self) -> float:
        tool_steps = [s for s in self.steps if s.action == "tool_execute"]
        if not tool_steps:
            return 1.0
        return sum(1 for s in tool_steps if s.success) / len(tool_steps)

    def bottleneck(self) -> Optional[StepProfile]:
        """Return the slowest step."""
        if not self.steps:
            return None
        return max(self.steps, key=lambda s: s.duration_ms)

    def summary(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "step_count": len(self.steps),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "tokens_per_second": self.tokens_per_second,
            "llm_time_ms": round(self.llm_time_ms, 1),
            "tool_time_ms": round(self.tool_time_ms, 1),
            "approval_time_ms": round(self.approval_time_ms, 1),
            "tool_success_rate": round(self.tool_success_rate, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 1),
            "bottleneck": self.bottleneck().to_dict() if self.bottleneck() else None,
        }


class AgentProfiler:
    """Performance profiler for agent runs.

    Usage:
        profiler = AgentProfiler()

        # Start a run
        profiler.start_run("run_123")

        # Record steps
        profiler.begin_step("llm_call")
        ...  # LLM call happens
        profiler.end_step(input_tokens=500, output_tokens=200)

        profiler.begin_step("tool_execute", tool_name="read_file")
        ...  # Tool execution
        profiler.end_step(success=True)

        # Finish and get report
        report = profiler.finish_run()
    """

    MAX_HISTORY = 50

    def __init__(self) -> None:
        self._current_run: Optional[RunProfile] = None
        self._current_step: Optional[StepProfile] = None
        self._history: deque[RunProfile] = deque(maxlen=self.MAX_HISTORY)
        self._lock = threading.Lock()

        # Rolling throughput window (last 20 data points)
        self._throughput_window: deque[Dict[str, float]] = deque(maxlen=20)

    def start_run(self, run_id: str = "") -> None:
        """Begin profiling a new agent run."""
        with self._lock:
            self._current_run = RunProfile(
                run_id=run_id,
                start_time=time.monotonic(),
            )
            self._current_step = None

    def begin_step(self, action: str, tool_name: str = "", **metadata: Any) -> None:
        """Mark the beginning of a step (LLM call, tool execution, etc.)."""
        with self._lock:
            if self._current_run is None:
                return
            self._current_step = StepProfile(
                index=len(self._current_run.steps),
                action=action,
                tool_name=tool_name,
                start_time=time.monotonic(),
                metadata=metadata,
            )

    def end_step(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        success: bool = True,
        error: str = "",
    ) -> None:
        """Mark the end of the current step."""
        with self._lock:
            if self._current_step is None or self._current_run is None:
                return
            self._current_step.end_time = time.monotonic()
            self._current_step.duration_ms = (
                self._current_step.end_time - self._current_step.start_time
            ) * 1000
            self._current_step.input_tokens = input_tokens
            self._current_step.output_tokens = output_tokens
            self._current_step.success = success
            self._current_step.error = error

            self._current_run.steps.append(self._current_step)
            self._current_run.total_input_tokens += input_tokens
            self._current_run.total_output_tokens += output_tokens

            # Track throughput
            if self._current_step.action == "llm_call" and self._current_step.duration_ms > 0:
                tps = output_tokens / (self._current_step.duration_ms / 1000)
                self._throughput_window.append({
                    "tps": tps,
                    "timestamp": time.time(),
                })

            # Track peak memory
            try:
                import psutil
                process = psutil.Process()
                mem_mb = process.memory_info().rss / (1024 * 1024)
                if mem_mb > self._current_run.peak_memory_mb:
                    self._current_run.peak_memory_mb = mem_mb
            except Exception:
                pass

            self._current_step = None

    def record_metric(self, name: str, value: float) -> None:
        """Record an arbitrary metric on the current step."""
        with self._lock:
            if self._current_step:
                self._current_step.metadata[name] = value

    def finish_run(self) -> Dict[str, Any]:
        """Finish the current run and return its summary."""
        with self._lock:
            if self._current_run is None:
                return {}
            self._current_run.end_time = time.monotonic()
            summary = self._current_run.summary()
            self._history.append(self._current_run)
            self._current_run = None
            self._current_step = None
            return summary

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get summaries of recent runs."""
        with self._lock:
            runs = list(self._history)
        return [r.summary() for r in runs[-limit:]]

    def get_throughput_history(self) -> List[Dict[str, float]]:
        """Get rolling token throughput data for charting."""
        with self._lock:
            return list(self._throughput_window)

    def get_step_breakdown(self, limit: int = 1) -> List[Dict[str, Any]]:
        """Get detailed step breakdown for the most recent run(s)."""
        with self._lock:
            runs = list(self._history)
        result = []
        for run in runs[-limit:]:
            result.append({
                "run_id": run.run_id,
                "steps": [s.to_dict() for s in run.steps],
                "total_duration_ms": round(run.total_duration_ms, 1),
                "bottleneck": run.bottleneck().to_dict() if run.bottleneck() else None,
            })
        return result

    def analyze_bottlenecks(self) -> Dict[str, Any]:
        """Analyze patterns across all profiled runs to find recurring bottlenecks."""
        with self._lock:
            runs = list(self._history)

        if not runs:
            return {"bottlenecks": [], "suggestions": []}

        # Aggregate step-level stats
        step_stats: Dict[str, List[float]] = {}
        tool_stats: Dict[str, List[float]] = {}
        total_llm_ms = 0.0
        total_tool_ms = 0.0
        total_approval_ms = 0.0
        total_steps = 0

        for run in runs:
            for step in run.steps:
                total_steps += 1
                action = step.action
                if action not in step_stats:
                    step_stats[action] = []
                step_stats[action].append(step.duration_ms)

                if action == "llm_call":
                    total_llm_ms += step.duration_ms
                elif action == "tool_execute":
                    total_tool_ms += step.duration_ms
                    if step.tool_name:
                        if step.tool_name not in tool_stats:
                            tool_stats[step.tool_name] = []
                        tool_stats[step.tool_name].append(step.duration_ms)
                elif action == "approval_wait":
                    total_approval_ms += step.duration_ms

        bottlenecks = []
        suggestions = []

        # Find slowest action type
        if step_stats:
            slowest = max(step_stats.items(), key=lambda x: sum(x[1]) / len(x[1]))
            avg_ms = sum(slowest[1]) / len(slowest[1])
            if avg_ms > 5000:
                bottlenecks.append({
                    "type": "slow_action",
                    "action": slowest[0],
                    "avg_ms": round(avg_ms, 1),
                    "count": len(slowest[1]),
                })

        # Find slowest individual tool
        if tool_stats:
            slowest_tool = max(tool_stats.items(), key=lambda x: sum(x[1]) / len(x[1]))
            avg_ms = sum(slowest_tool[1]) / len(slowest_tool[1])
            if avg_ms > 3000:
                bottlenecks.append({
                    "type": "slow_tool",
                    "tool": slowest_tool[0],
                    "avg_ms": round(avg_ms, 1),
                    "count": len(slowest_tool[1]),
                })

        # Approval wait analysis
        if total_approval_ms > 10000:
            bottlenecks.append({
                "type": "approval_bottleneck",
                "total_ms": round(total_approval_ms, 1),
            })
            suggestions.append("Consider batch-approving tools or reducing approval frequency")

        # Time breakdown suggestions
        total_time = total_llm_ms + total_tool_ms + total_approval_ms
        if total_time > 0:
            llm_pct = total_llm_ms / total_time
            tool_pct = total_tool_ms / total_time
            if llm_pct > 0.8:
                suggestions.append("LLM calls dominate runtime — consider faster inference or smaller context")
            if tool_pct > 0.5:
                suggestions.append("Tool execution dominates — consider caching or batching reads")

        return {
            "total_runs": len(runs),
            "total_steps": total_steps,
            "time_breakdown": {
                "llm_ms": round(total_llm_ms, 1),
                "tool_ms": round(total_tool_ms, 1),
                "approval_ms": round(total_approval_ms, 1),
                "llm_pct": round(total_llm_ms / total_time * 100, 1) if total_time > 0 else 0,
                "tool_pct": round(total_tool_ms / total_time * 100, 1) if total_time > 0 else 0,
            },
            "bottlenecks": bottlenecks,
            "suggestions": suggestions,
        }
