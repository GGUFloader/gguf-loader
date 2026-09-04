"""
ToolAnalytics - Track and optimize tool usage patterns.

Pattern from: Aider's repo-map optimization + SWE-agent action stats.
Analyzes tool usage to provide insights on:
- Most/least used tools
- Average execution time per tool
- Success/failure rates per tool
- Tool call sequences (what tools are called together)
- Optimization suggestions (tool X could replace tool Y)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ToolCall:
    """Record of a single tool call."""

    def __init__(self, tool: str, params: Dict[str, Any], status: str,
                 duration_ms: int = 0, result_summary: str = "") -> None:
        self.tool = tool
        self.params = params
        self.status = status
        self.duration_ms = duration_ms
        self.result_summary = result_summary
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


class ToolAnalytics:
    """Track and analyze tool usage.

    Usage:
        analytics = ToolAnalytics()

        # Record tool calls
        analytics.record("read_file", {}, "success", 50)
        analytics.record("search_files", {"pattern": "foo"}, "success", 200)

        # Get insights
        report = analytics.get_report()
        suggestions = analytics.get_suggestions()
    """

    def __init__(self) -> None:
        self._calls: List[ToolCall] = []
        self._by_tool: Dict[str, List[ToolCall]] = defaultdict(list)
        self._sequences: List[List[str]] = []  # tool call sequences per step
        self._current_sequence: List[str] = []

    def record(self, tool: str, params: Dict[str, Any], status: str,
               duration_ms: int = 0, result_summary: str = "") -> None:
        """Record a tool call."""
        call = ToolCall(tool, params, status, duration_ms, result_summary)
        self._calls.append(call)
        self._by_tool[tool].append(call)
        self._current_sequence.append(tool)

    def end_step(self) -> None:
        """Mark the end of a step (tool call sequence)."""
        if self._current_sequence:
            self._sequences.append(self._current_sequence)
            self._current_sequence = []

    def get_report(self) -> Dict[str, Any]:
        """Generate a full usage report."""
        total = len(self._calls)
        if total == 0:
            return {"total_calls": 0}

        # Per-tool stats
        tool_stats: Dict[str, Dict[str, Any]] = {}
        for tool, calls in self._by_tool.items():
            successes = sum(1 for c in calls if c.status == "success")
            failures = sum(1 for c in calls if c.status == "error")
            durations = [c.duration_ms for c in calls if c.duration_ms > 0]
            avg_duration = sum(durations) / len(durations) if durations else 0
            max_duration = max(durations) if durations else 0

            tool_stats[tool] = {
                "total": len(calls),
                "successes": successes,
                "failures": failures,
                "success_rate": round(successes / len(calls) * 100, 1),
                "avg_duration_ms": round(avg_duration),
                "max_duration_ms": max_duration,
            }

        # Sort by usage
        sorted_tools = sorted(tool_stats.items(), key=lambda x: -x[1]["total"])

        # Most common sequences
        seq_counts: Dict[str, int] = defaultdict(int)
        for seq in self._sequences:
            if len(seq) >= 2:
                key = " → ".join(seq[:3])
                seq_counts[key] += 1
        top_sequences = sorted(seq_counts.items(), key=lambda x: -x[1])[:5]

        # Overall stats
        total_success = sum(1 for c in self._calls if c.status == "success")
        total_fail = sum(1 for c in self._calls if c.status == "error")
        all_durations = [c.duration_ms for c in self._calls if c.duration_ms > 0]

        return {
            "total_calls": total,
            "success_rate": round(total_success / total * 100, 1),
            "avg_duration_ms": round(sum(all_durations) / len(all_durations)) if all_durations else 0,
            "by_tool": {k: v for k, v in sorted_tools},
            "top_sequences": [{"sequence": s, "count": c} for s, c in top_sequences],
            "unique_tools": len(self._by_tool),
        }

    def get_suggestions(self) -> List[str]:
        """Get optimization suggestions based on usage patterns."""
        suggestions = []

        # Check for redundant read_file calls
        reads = self._by_tool.get("read_file", [])
        read_paths = [c.params.get("path", "") for c in reads]
        if len(read_paths) != len(set(read_paths)):
            dupes = len(read_paths) - len(set(read_paths))
            suggestions.append(
                f"Read {dupes} duplicate file(s) — cache results to avoid re-reading"
            )

        # Check for search then read pattern
        searches = self._by_tool.get("search_files", [])
        if searches:
            suggestions.append(
                "Consider using search_files with context_lines instead of "
                "separate read_file calls"
            )

        # Check for high failure rates
        for tool, calls in self._by_tool.items():
            if len(calls) >= 3:
                fail_rate = sum(1 for c in calls if c.status == "error") / len(calls)
                if fail_rate > 0.5:
                    suggestions.append(
                        f"Tool '{tool}' has {fail_rate:.0%} failure rate — "
                        "check parameters or use a different approach"
                    )

        # Check for slow tools
        for tool, calls in self._by_tool.items():
            durations = [c.duration_ms for c in calls if c.duration_ms > 0]
            if durations:
                avg = sum(durations) / len(durations)
                if avg > 5000:
                    suggestions.append(
                        f"Tool '{tool}' averages {avg/1000:.1f}s — "
                        "consider batching or using a faster alternative"
                    )

        # Check for missing batch opportunities
        writes = self._by_tool.get("write_file", [])
        return suggestions

    def get_tool_rankings(self) -> List[Dict[str, Any]]:
        """Get tools ranked by usage."""
        report = self.get_report()
        by_tool = report.get("by_tool", {})
        return [
            {"tool": tool, **stats}
            for tool, stats in sorted(by_tool.items(), key=lambda x: -x[1]["total"])
        ]

    def get_slowest_tools(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the slowest tools by average duration."""
        report = self.get_report()
        by_tool = report.get("by_tool", {})
        sorted_tools = sorted(
            by_tool.items(),
            key=lambda x: -x[1]["avg_duration_ms"],
        )
        return [
            {"tool": tool, "avg_ms": stats["avg_duration_ms"]}
            for tool, stats in sorted_tools[:limit]
            if stats["avg_duration_ms"] > 0
        ]

    def get_stats(self) -> Dict[str, Any]:
        report = self.get_report()
        return {
            "total_calls": report["total_calls"],
            "unique_tools": report["unique_tools"],
            "success_rate": report["success_rate"],
            "sequences": len(self._sequences),
        }
