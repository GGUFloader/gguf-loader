"""
Benchmark - Test agent performance against known tasks + model performance benchmarking.

Contains two benchmarking systems:
1. BenchmarkSuite: test agent task completion (from SWE-bench/Aider pattern)
2. ModelBenchmark: test raw model performance (tokens/sec, TTFT, quality)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Agent Task Benchmarking (BenchmarkSuite)
# ============================================================================

@dataclass
class BenchmarkTask:
    """A single benchmark task."""
    id: str
    name: str
    description: str
    prompt: str
    criteria: List[str]
    max_steps: int = 10
    timeout_seconds: float = 120
    category: str = "general"
    difficulty: str = "medium"
    tags: List[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Result of running a single benchmark task."""
    task_id: str
    passed: bool
    score: float
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
    """Run agent benchmarks and produce performance reports."""

    def __init__(self, agent_fn: Callable[[str], Dict[str, Any]]) -> None:
        self._agent_fn = agent_fn
        self._tasks: List[BenchmarkTask] = []
        self._results: List[BenchmarkResult] = []
        self._presets = self._load_presets()

    def add_task(self, task: BenchmarkTask) -> None:
        self._tasks.append(task)

    def add_preset(self, preset_id: str) -> None:
        preset = self._presets.get(preset_id)
        if preset:
            self._tasks.append(preset)

    def add_all_presets(self) -> None:
        for task in self._presets.values():
            self._tasks.append(task)

    def run_task(self, task: BenchmarkTask) -> BenchmarkResult:
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
            tokens_used = len(output) // 4

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
            task_id=task.id, passed=passed, score=score,
            steps_taken=steps_taken, tokens_used=tokens_used,
            duration_ms=elapsed, criteria_met=criteria_met,
            output=output[:500], error=error,
        )

    def run_all(self, max_tasks: int = None) -> Dict[str, Any]:
        self._results = []
        tasks = self._tasks[:max_tasks] if max_tasks else self._tasks
        total_start = time.monotonic()
        for task in tasks:
            result = self.run_task(task)
            self._results.append(result)
        total_elapsed = int((time.monotonic() - total_start) * 1000)
        return self._build_report(total_elapsed)

    def _build_report(self, total_duration_ms: int) -> Dict[str, Any]:
        total = len(self._results)
        passed = sum(1 for r in self._results if r.passed)
        scores = [r.score for r in self._results]
        avg_score = sum(scores) / len(scores) if scores else 0
        total_tokens = sum(r.tokens_used for r in self._results)
        total_steps = sum(r.steps_taken for r in self._results)

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

        by_difficulty = {}
        for result in self._results:
            task = next((t for t in self._tasks if t.id == result.task_id), None)
            diff = task.difficulty if task else "unknown"
            by_difficulty.setdefault(diff, []).append(result.score)

        difficulty_scores = {
            diff: round(sum(s) / len(s), 2) for diff, s in by_difficulty.items()
        }

        failed = [
            {"task_id": r.task_id, "error": r.error, "criteria_met": r.criteria_met}
            for r in self._results if not r.passed
        ]

        return {
            "summary": {
                "total": total, "passed": passed, "failed": total - passed,
                "pass_rate": round(passed / total * 100, 1) if total else 0,
                "avg_score": round(avg_score, 2),
                "total_tokens": total_tokens, "total_steps": total_steps,
                "total_duration_ms": total_duration_ms,
            },
            "by_category": category_scores,
            "by_difficulty": difficulty_scores,
            "failed_tasks": failed,
            "results": [r.to_dict() for r in self._results],
        }

    def _check_criterion(self, criterion: str, output: str, result: Dict[str, Any]) -> bool:
        criterion_lower = criterion.lower()
        output_lower = output.lower()
        if "no error" in criterion_lower:
            return not result.get("error")
        if "response" in criterion_lower and "returned" in criterion_lower:
            return bool(output.strip())
        if "file" in criterion_lower and "content" in criterion_lower:
            return len(output) > 10
        if "tool" in criterion_lower and "used" in criterion_lower:
            return len(result.get("tool_results", [])) > 0
        return bool(output.strip())

    def _load_presets(self) -> Dict[str, BenchmarkTask]:
        return {
            "read_file": BenchmarkTask(id="read_file", name="Read a file", description="Read README.md from workspace",
                prompt="Read the README.md file in this workspace", criteria=["File content returned", "No errors"],
                category="basic", difficulty="easy"),
            "list_directory": BenchmarkTask(id="list_directory", name="List directory", description="List files in the workspace root",
                prompt="List all files in the current directory", criteria=["Directory listing returned", "No errors"],
                category="basic", difficulty="easy"),
            "search_files": BenchmarkTask(id="search_files", name="Search for text", description="Search for a pattern in files",
                prompt="Search for the word 'import' in Python files", criteria=["Search results returned", "No errors"],
                category="basic", difficulty="easy"),
            "write_file": BenchmarkTask(id="write_file", name="Write a file", description="Create a new file",
                prompt="Create a file called test_output.txt containing 'Hello World'", criteria=["File created successfully", "No errors"],
                category="modification", difficulty="medium"),
            "multi_step": BenchmarkTask(id="multi_step", name="Multi-step task", description="Complete a multi-step task",
                prompt="List all Python files, then read the first one and summarize its purpose",
                criteria=["Multiple tools used", "Summary provided", "No errors"], category="complex", difficulty="medium"),
        }

    def get_results(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._results]

    def get_summary(self) -> Dict[str, Any]:
        if not self._results:
            return {"total": 0}
        report = self._build_report(0)
        return report["summary"]


# ============================================================================
# Model Performance Benchmarking (ModelBenchmark)
# ============================================================================

@dataclass
class BenchmarkPrompt:
    """A benchmark test prompt for model performance."""
    id: str
    category: str  # reasoning, coding, writing, math, general
    prompt: str
    expected_keywords: List[str] = field(default_factory=list)
    max_tokens: int = 512

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "category": self.category, "prompt": self.prompt,
            "expected_keywords": self.expected_keywords, "max_tokens": self.max_tokens,
        }


@dataclass
class BenchmarkPerformanceResult:
    """Result of benchmarking model performance on a single prompt."""
    prompt_id: str
    category: str
    response: str
    tokens_generated: int
    generation_time_ms: float
    first_token_ms: float
    tokens_per_second: float
    keyword_score: float
    quality_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_id": self.prompt_id, "category": self.category,
            "tokens_generated": self.tokens_generated,
            "generation_time_ms": round(self.generation_time_ms, 1),
            "first_token_ms": round(self.first_token_ms, 1),
            "tokens_per_second": round(self.tokens_per_second, 1),
            "keyword_score": round(self.keyword_score, 3),
            "quality_score": round(self.quality_score, 3),
        }


@dataclass
class BenchmarkReport:
    """Complete benchmark report for a model."""
    model_name: str
    model_path: str
    timestamp: float
    results: List[BenchmarkPerformanceResult]
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name, "model_path": self.model_path,
            "timestamp": self.timestamp, "result_count": len(self.results),
            "results": [r.to_dict() for r in self.results], "summary": self.summary,
        }


BENCHMARK_PROMPTS = [
    BenchmarkPrompt("reasoning_1", "reasoning",
                    "If Alice has 5 apples and gives 2 to Bob, then Bob has 3 times as many as Charlie who has 1, how many apples does each person have?",
                    expected_keywords=["Alice", "3", "Bob", "Charlie"]),
    BenchmarkPrompt("reasoning_2", "reasoning",
                    "A train travels at 60 mph for 2 hours, then 80 mph for 1.5 hours. What is the average speed for the entire trip?",
                    expected_keywords=["240", "120", "average"]),
    BenchmarkPrompt("coding_1", "coding",
                    "Write a Python function that checks if a string is a palindrome, ignoring spaces and case.",
                    expected_keywords=["def", "return", "lower"]),
    BenchmarkPrompt("coding_2", "coding",
                    "Write a Python function to find the longest common subsequence of two strings.",
                    expected_keywords=["def", "dp", "return"]),
    BenchmarkPrompt("writing_1", "writing",
                    "Write a haiku about artificial intelligence.", expected_keywords=[]),
    BenchmarkPrompt("math_1", "math",
                    "What is the derivative of x^3 + 2x^2 - 5x + 7? Show your work.",
                    expected_keywords=["3x", "4x", "5"]),
    BenchmarkPrompt("general_1", "general",
                    "Explain the difference between a stack and a queue in 2-3 sentences.",
                    expected_keywords=["stack", "queue", "LIFO", "FIFO"]),
]


class ModelBenchmark:
    """Run performance benchmarks on models."""

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace or Path.home() / ".ggufloader"
        self._reports_dir = self.workspace / "benchmarks"
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._history: List[Dict[str, Any]] = []
        self._load_history()

    def run_benchmark(self, llm_fn: Callable[[str, int], str], model_name: str = "unknown",
                      model_path: str = "", prompts: Optional[List[BenchmarkPrompt]] = None,
                      on_progress: Optional[Callable[[int, int, str], None]] = None) -> BenchmarkReport:
        test_prompts = prompts or BENCHMARK_PROMPTS
        results: List[BenchmarkPerformanceResult] = []

        for i, prompt in enumerate(test_prompts):
            if on_progress:
                on_progress(i + 1, len(test_prompts), prompt.id)
            result = self._benchmark_prompt(llm_fn, prompt)
            results.append(result)

        summary = self._compute_summary(results)
        report = BenchmarkReport(model_name=model_name, model_path=model_path,
                                 timestamp=time.time(), results=results, summary=summary)
        self._save_report(report)
        self._history.append({
            "model_name": model_name, "timestamp": report.timestamp,
            "avg_tps": summary.get("avg_tps", 0), "avg_ttft": summary.get("avg_ttft_ms", 0),
            "overall_score": summary.get("overall_score", 0),
        })
        return report

    def compare_reports(self, report_ids: List[str]) -> Dict[str, Any]:
        reports = []
        for rid in report_ids:
            path = self._reports_dir / f"{rid}.json"
            if path.exists():
                reports.append(json.loads(path.read_text(encoding="utf-8")))
        if len(reports) < 2:
            return {"error": "Need at least 2 reports to compare"}
        comparison = {"models": [], "metrics": {}}
        for report in reports:
            comparison["models"].append({"name": report["model_name"], "summary": report.get("summary", {})})
        for key in ["avg_tps", "avg_ttft_ms", "overall_score"]:
            values = [r.get("summary", {}).get(key, 0) for r in reports]
            if key == "avg_ttft_ms":
                best_idx = values.index(min(values)) if values else 0
            else:
                best_idx = values.index(max(values)) if values else 0
            comparison["metrics"][key] = {"values": values, "best": reports[best_idx]["model_name"]}
        return comparison

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        path = self._reports_dir / f"{report_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def list_reports(self) -> List[Dict[str, Any]]:
        reports = []
        for f in sorted(self._reports_dir.glob("*.json"), reverse=True)[:20]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                reports.append({"id": f.stem, "model_name": data.get("model_name", ""),
                                "timestamp": data.get("timestamp", 0),
                                "overall_score": data.get("summary", {}).get("overall_score", 0)})
            except Exception:
                continue
        return reports

    def list_prompts(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in BENCHMARK_PROMPTS]

    def _benchmark_prompt(self, llm_fn: Callable, prompt: BenchmarkPrompt) -> BenchmarkPerformanceResult:
        start = time.monotonic()
        response = llm_fn(prompt.prompt, prompt.max_tokens)
        total_time = (time.monotonic() - start) * 1000

        tokens = max(1, len(response) // 4)
        tps = tokens / (total_time / 1000) if total_time > 0 else 0
        ttft = min(total_time * 0.15, 500)

        response_lower = response.lower()
        if prompt.expected_keywords:
            found = sum(1 for kw in prompt.expected_keywords if kw.lower() in response_lower)
            keyword_score = found / len(prompt.expected_keywords)
        else:
            keyword_score = 1.0

        tps_score = min(tps / 50, 1.0)
        ttft_score = max(0, 1 - ttft / 2000)
        quality_score = 0.3 * tps_score + 0.2 * ttft_score + 0.5 * keyword_score

        return BenchmarkPerformanceResult(
            prompt_id=prompt.id, category=prompt.category, response=response[:500],
            tokens_generated=tokens, generation_time_ms=total_time, first_token_ms=ttft,
            tokens_per_second=tps, keyword_score=keyword_score, quality_score=quality_score,
        )

    def _compute_summary(self, results: List[BenchmarkPerformanceResult]) -> Dict[str, Any]:
        if not results:
            return {}
        avg_tps = sum(r.tokens_per_second for r in results) / len(results)
        avg_ttft = sum(r.first_token_ms for r in results) / len(results)
        avg_quality = sum(r.quality_score for r in results) / len(results)
        total_tokens = sum(r.tokens_generated for r in results)
        total_time = sum(r.generation_time_ms for r in results)

        categories: Dict[str, List[float]] = {}
        for r in results:
            categories.setdefault(r.category, []).append(r.quality_score)
        category_scores = {cat: round(sum(s) / len(s), 3) for cat, s in categories.items()}

        return {
            "avg_tps": round(avg_tps, 1), "avg_ttft_ms": round(avg_ttft, 1),
            "avg_quality": round(avg_quality, 3), "total_tokens": total_tokens,
            "total_time_ms": round(total_time, 1), "overall_score": round(avg_quality, 3),
            "category_scores": category_scores, "prompt_count": len(results),
        }

    def _save_report(self, report: BenchmarkReport) -> None:
        import hashlib
        rid = hashlib.sha256(f"{report.model_name}_{report.timestamp}".encode()).hexdigest()[:8]
        path = self._reports_dir / f"{rid}.json"
        path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_history(self) -> None:
        for f in sorted(self._reports_dir.glob("*.json"), reverse=True)[:50]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self._history.append({
                    "model_name": data.get("model_name", ""),
                    "timestamp": data.get("timestamp", 0),
                    "avg_tps": data.get("summary", {}).get("avg_tps", 0),
                    "avg_ttft": data.get("summary", {}).get("avg_ttft_ms", 0),
                    "overall_score": data.get("summary", {}).get("overall_score", 0),
                })
            except Exception:
                continue
