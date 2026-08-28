"""
Benchmark - Test agent performance against known tasks.

Pattern from: SWE-bench + Aider benchmark suite.
Runs the agent on a set of predefined tasks and measures:
- Success rate (task completed correctly)
- Efficiency (steps taken vs minimum)
- Quality (output meets criteria)
- Speed (time to completion)
- Cost (tokens consumed)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkTask:
    """A single benchmark task."""
    id: str
    name: str
    description: str
    prompt: str  # The user message to send
    criteria: List[str]  # Success criteria
    max_steps: int = 10
    timeout_seconds: float = 120
    category: str = "general"
    difficulty: str = "medium"  # easy, medium, hard
    tags: List[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Result of running a single benchmark task."""
    task_id: str
    passed: bool
    score: float  # 0.0 to 1.0
    steps_taken: int
    tokens_used: int
    duration_ms: int
    criteria_met: List[bool]
    output: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "score": round(self.score, 2),
            "steps": self.steps_taken,
            "tokens": self.tokens_used,
            "duration_ms": self.duration_ms,
            "criteria_met": self.criteria_met,
            "error": self.error,
        }


class BenchmarkSuite:
    """Run agent benchmarks and produce performance reports.

    Usage:
        suite = BenchmarkSuite(agent_fn)

        # Add tasks
        suite.add_task(BenchmarkTask(
            id="read_file",
            name="Read a file",
            prompt="Read the README.md file",
            criteria=["File content returned", "No errors"],
        ))

        # Run all tasks
        report = suite.run_all()
        print(report["summary"])
    """

    def __init__(self, agent_fn: Callable[[str], Dict[str, Any]]) -> None:
        """Initialize with the agent function to test.

        Args:
            agent_fn: Callable that takes a prompt string and returns
                     {"response": str, "tool_results": [...]}
        """
        self._agent_fn = agent_fn
        self._tasks: List[BenchmarkTask] = []
        self._results: List[BenchmarkResult] = []
        self._presets = self._load_presets()

    def add_task(self, task: BenchmarkTask) -> None:
        self._tasks.append(task)

    def add_preset(self, preset_id: str) -> None:
        """Add a preset benchmark task."""
        preset = self._presets.get(preset_id)
        if preset:
            self._tasks.append(preset)

    def add_all_presets(self) -> None:
        """Add all preset benchmark tasks."""
        for task in self._presets.values():
            self._tasks.append(task)

    def run_task(self, task: BenchmarkTask) -> BenchmarkResult:
        """Run a single benchmark task."""
        start = time.monotonic()
        steps_taken = 0
        tokens_used = 0
        criteria_met = []
        output = ""
        error = None

        try:
            result = self._agent_fn(task.prompt)
            output = result.get("response", "")
            steps_taken = len(result.get("tool_results", []))
            tokens_used = len(output) // 4  # rough estimate

            # Check criteria
            for criterion in task.criteria:
                met = self._check_criterion(criterion, output, result)
                criteria_met.append(met)

        except Exception as e:
            error = str(e)
            criteria_met = [False] * len(task.criteria)

        elapsed = int((time.monotonic() - start) * 1000)
        passed = all(criteria_met) if criteria_met else False
        score = sum(criteria_met) / len(criteria_met) if criteria_met else 0.0

        return BenchmarkResult(
            task_id=task.id,
            passed=passed,
            score=score,
            steps_taken=steps_taken,
            tokens_used=tokens_used,
            duration_ms=elapsed,
            criteria_met=criteria_met,
            output=output[:500],
            error=error,
        )

    def run_all(self, max_tasks: int = None) -> Dict[str, Any]:
        """Run all benchmark tasks."""
        self._results = []
        tasks = self._tasks[:max_tasks] if max_tasks else self._tasks
        total_start = time.monotonic()

        for task in tasks:
            logger.info("Running benchmark: %s", task.name)
            result = self.run_task(task)
            self._results.append(result)

        total_elapsed = int((time.monotonic() - total_start) * 1000)
        return self._build_report(total_elapsed)

    def _build_report(self, total_duration_ms: int) -> Dict[str, Any]:
        """Build a comprehensive benchmark report."""
        total = len(self._results)
        passed = sum(1 for r in self._results if r.passed)
        scores = [r.score for r in self._results]
        avg_score = sum(scores) / len(scores) if scores else 0

        total_tokens = sum(r.tokens_used for r in self._results)
        total_steps = sum(r.steps_taken for r in self._results)

        # By category
        by_category: Dict[str, List[BenchmarkResult]] = {}
        for result in self._results:
            task = next((t for t in self._tasks if t.id == result.task_id), None)
            cat = task.category if task else "unknown"
            by_category.setdefault(cat, []).append(result)

        category_scores = {}
        for cat, results in by_category.items():
            cat_scores = [r.score for r in results]
            category_scores[cat] = {
                "count": len(results),
                "passed": sum(1 for r in results if r.passed),
                "avg_score": round(sum(cat_scores) / len(cat_scores), 2),
            }

        # By difficulty
        by_difficulty = {}
        for result in self._results:
            task = next((t for t in self._tasks if t.id == result.task_id), None)
            diff = task.difficulty if task else "unknown"
            by_difficulty.setdefault(diff, []).append(result.score)

        difficulty_scores = {
            diff: round(sum(scores) / len(scores), 2)
            for diff, scores in by_difficulty.items()
        }

        # Failed tasks
        failed = [
            {"task_id": r.task_id, "error": r.error, "criteria_met": r.criteria_met}
            for r in self._results if not r.passed
        ]

        return {
            "summary": {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": round(passed / total * 100, 1) if total else 0,
                "avg_score": round(avg_score, 2),
                "total_tokens": total_tokens,
                "total_steps": total_steps,
                "total_duration_ms": total_duration_ms,
            },
            "by_category": category_scores,
            "by_difficulty": difficulty_scores,
            "failed_tasks": failed,
            "results": [r.to_dict() for r in self._results],
        }

    def _check_criterion(self, criterion: str, output: str,
                         result: Dict[str, Any]) -> bool:
        """Check if a criterion is met."""
        criterion_lower = criterion.lower()
        output_lower = output.lower()

        # Simple keyword matching
        if "no error" in criterion_lower:
            return not result.get("error")
        if "response" in criterion_lower and "returned" in criterion_lower:
            return bool(output.strip())
        if "file" in criterion_lower and "content" in criterion_lower:
            return len(output) > 10
        if "tool" in criterion_lower and "used" in criterion_lower:
            return len(result.get("tool_results", [])) > 0
        if "correct" in criterion_lower:
            return bool(output.strip())
        if "complete" in criterion_lower:
            return bool(output.strip())

        # Default: check if output contains any meaningful content
        return bool(output.strip())

    def _load_presets(self) -> Dict[str, BenchmarkTask]:
        """Load preset benchmark tasks."""
        return {
            "read_file": BenchmarkTask(
                id="read_file", name="Read a file",
                description="Read README.md from workspace",
                prompt="Read the README.md file in this workspace",
                criteria=["File content returned", "No errors"],
                category="basic", difficulty="easy",
            ),
            "list_directory": BenchmarkTask(
                id="list_directory", name="List directory",
                description="List files in the workspace root",
                prompt="List all files in the current directory",
                criteria=["Directory listing returned", "No errors"],
                category="basic", difficulty="easy",
            ),
            "search_files": BenchmarkTask(
                id="search_files", name="Search for text",
                description="Search for a pattern in files",
                prompt="Search for the word 'import' in Python files",
                criteria=["Search results returned", "No errors"],
                category="basic", difficulty="easy",
            ),
            "write_file": BenchmarkTask(
                id="write_file", name="Write a file",
                description="Create a new file",
                prompt="Create a file called test_output.txt containing 'Hello World'",
                criteria=["File created successfully", "No errors"],
                category="modification", difficulty="medium",
            ),
            "multi_step": BenchmarkTask(
                id="multi_step", name="Multi-step task",
                description="Complete a multi-step task",
                prompt="List all Python files, then read the first one and summarize its purpose",
                criteria=["Multiple tools used", "Summary provided", "No errors"],
                category="complex", difficulty="medium",
            ),
        }

    def get_results(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._results]

    def get_summary(self) -> Dict[str, Any]:
        if not self._results:
            return {"total": 0}
        report = self._build_report(0)
        return report["summary"]
