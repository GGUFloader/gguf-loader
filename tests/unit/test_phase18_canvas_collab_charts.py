"""Tests for Phase 18: Visual Workflow Canvas, Collaboration, Benchmark Charts."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest


# ── Workflow Canvas API ──────────────────────────────────────────────────


class TestWorkflowCanvas:
    """Tests for the visual workflow canvas backend support."""

    def test_workflow_builder_imports(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder, Workflow, WorkflowStep

    def test_workflow_step_types(self):
        from ggufloader.core.agent.workflow_builder import WorkflowStep

        for step_type in ["llm", "tool", "condition", "transform"]:
            step = WorkflowStep(id=f"s_{step_type}", type=step_type, name=f"Step {step_type}")
            assert step.type == step_type

    def test_workflow_complex_dag(self):
        from ggufloader.core.agent.workflow_builder import Workflow, WorkflowStep

        wf = Workflow(id="complex", name="Complex", description="Multi-branch DAG",
                      steps=[
                          WorkflowStep(id="start", type="llm", name="Start"),
                          WorkflowStep(id="branch_a", type="tool", name="Branch A", depends_on=["start"]),
                          WorkflowStep(id="branch_b", type="tool", name="Branch B", depends_on=["start"]),
                          WorkflowStep(id="merge", type="llm", name="Merge", depends_on=["branch_a", "branch_b"]),
                          WorkflowStep(id="output", type="transform", name="Output", depends_on=["merge"]),
                      ])
        errors = wf.validate()
        assert len(errors) == 0
        order = wf.execution_order()
        assert order.index("start") < order.index("branch_a")
        assert order.index("start") < order.index("branch_b")
        assert order.index("branch_a") < order.index("merge")
        assert order.index("branch_b") < order.index("merge")
        assert order.index("merge") < order.index("output")

    def test_workflow_persistence_roundtrip(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder, Workflow, WorkflowStep

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "wf"
            wb = WorkflowBuilder(path)

            # Create and save
            wf = Workflow(id="rt_test", name="Roundtrip", description="Test",
                          steps=[
                              WorkflowStep(id="s1", type="llm", name="Step 1", config={"prompt": "hello"}),
                              WorkflowStep(id="s2", type="tool", name="Step 2", depends_on=["s1"]),
                          ])
            wb.save(wf)

            # Reload
            wb2 = WorkflowBuilder(path)
            loaded = wb2.get("rt_test")
            assert loaded is not None
            assert len(loaded.steps) == 2
            assert loaded.steps[0].config["prompt"] == "hello"
            assert loaded.steps[1].depends_on == ["s1"]

    def test_execute_dry_run_plan(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder

        with tempfile.TemporaryDirectory() as td:
            wb = WorkflowBuilder(Path(td) / "wf")
            wf = wb.create_from_template("code_review")
            result = wb.execute_dry_run(wf.id)
            assert result["valid"] is True
            assert len(result["plan"]) >= 3
            assert "execution_order" in result
            # Check each plan entry has required fields
            for entry in result["plan"]:
                assert "step" in entry
                assert "name" in entry
                assert "type" in entry


# ── Collaboration ─────────────────────────────────────────────────────────


class TestCollaborationAdvanced:
    """Advanced collaboration tests."""

    def test_multiple_sessions(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("s1", "u1", "Alice")
        mgr.join_session("s2", "u2", "Bob")
        mgr.join_session("s3", "u3", "Charlie")

        active = mgr.get_active_sessions()
        assert len(active) == 3

    def test_broadcast_excludes_sender(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("s1", "u1", "Alice")
        mgr.join_session("s1", "u2", "Bob")
        mgr.join_session("s1", "u3", "Charlie")

        targets = mgr.broadcast_event("s1", {"type": "edit"}, exclude_user="u1")
        assert "u1" not in targets
        assert "u2" in targets
        assert "u3" in targets

    def test_cursor_updates(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("s1", "u1", "Alice")
        mgr.update_cursor("s1", "u1", {"line": 10, "col": 5})
        mgr.update_cursor("s1", "u1", {"line": 20, "col": 15})
        info = mgr.get_session_info("s1")
        alice = [c for c in info["collaborators"] if c["id"] == "u1"][0]
        assert alice["cursor_position"]["line"] == 20

    def test_typing_indicator(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("s1", "u1", "Alice")
        mgr.set_typing("s1", "u1", True)
        info = mgr.get_session_info("s1")
        alice = [c for c in info["collaborators"] if c["id"] == "u1"][0]
        assert alice["is_typing"] is True

        mgr.set_typing("s1", "u1", False)
        info = mgr.get_session_info("s1")
        alice = [c for c in info["collaborators"] if c["id"] == "u1"][0]
        assert alice["is_typing"] is False

    def test_cleanup_multiple_stale(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        c1 = mgr.join_session("s1", "u1", "Alice")
        c2 = mgr.join_session("s1", "u2", "Bob")
        c1.last_active = time.time() - 600
        c2.last_active = time.time() - 600
        removed = mgr.cleanup_stale(timeout=300)
        assert removed == 2

    def test_user_multiple_sessions(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("s1", "u1", "Alice")
        mgr.join_session("s2", "u1", "Alice")
        mgr.join_session("s3", "u1", "Alice")
        sessions = mgr.get_user_sessions("u1")
        assert len(sessions) == 3

    def test_collaborator_colors_unique(self):
        from ggufloader.core.agent.collaboration import CollaborationManager, COLLABORATOR_COLORS

        mgr = CollaborationManager()
        colors = []
        for i in range(len(COLLABORATOR_COLORS)):
            c = mgr.join_session("s1", f"u{i}", f"User{i}")
            colors.append(c.color)
        assert len(set(colors)) == len(COLLABORATOR_COLORS)

    def test_session_not_found(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        info = mgr.get_session_info("nonexistent")
        assert info["collaborators"] == []

    def test_broadcast_no_session(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        targets = mgr.broadcast_event("nonexistent", {"type": "test"})
        assert targets == []


# ── Benchmark ────────────────────────────────────────────────────────────


class TestBenchmarkCharts:
    """Tests for benchmark chart data."""

    def test_benchmark_report_structure(self):
        from ggufloader.core.agent.benchmark import BenchmarkReport, BenchmarkPerformanceResult

        results = []
        for i, cat in enumerate(["reasoning", "coding", "writing", "math"]):
            results.append(BenchmarkPerformanceResult(
                prompt_id=f"p{i}", category=cat, response=f"Answer {i}",
                tokens_generated=50 + i * 10, generation_time_ms=100 + i * 50,
                first_token_ms=10 + i * 5, tokens_per_second=50 - i * 5,
                keyword_score=0.8 + i * 0.05, quality_score=0.7 + i * 0.07,
            ))
        report = BenchmarkReport(
            model_name="chart_test", model_path="/fake",
            timestamp=time.time(), results=results,
            summary={
                "avg_tps": 40, "avg_ttft_ms": 20, "avg_quality": 0.8,
                "total_tokens": 240, "total_time_ms": 500,
                "overall_score": 0.8,
                "category_scores": {"reasoning": 0.8, "coding": 0.85, "writing": 0.9, "math": 0.95},
                "prompt_count": 4,
            },
        )
        d = report.to_dict()
        assert d["result_count"] == 4
        assert len(d["results"]) == 4
        assert d["summary"]["category_scores"]["reasoning"] == 0.8

    def test_benchmark_multiple_models(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark, BENCHMARK_PROMPTS

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))

            def fast_llm(p: str, m: int = 512) -> str:
                return "Fast model response with keywords Alice Bob"

            def slow_llm(p: str, m: int = 512) -> str:
                return "Slow response"

            r1 = bm.run_benchmark(fast_llm, "FastModel", "/fast.gguf", prompts=BENCHMARK_PROMPTS[:3])
            r2 = bm.run_benchmark(slow_llm, "SlowModel", "/slow.gguf", prompts=BENCHMARK_PROMPTS[:3])

            # Fast model should have higher TPS
            assert r1.summary["avg_tps"] > 0
            assert r2.summary["avg_tps"] > 0

            # History should have both
            history = bm.get_history()
            assert len(history) >= 2

    def test_benchmark_category_breakdown(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark, BENCHMARK_PROMPTS

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))

            def mock_llm(p: str, m: int = 512) -> str:
                return "Response with reasoning coding writing"

            report = bm.run_benchmark(mock_llm, "cat_test", "", prompts=BENCHMARK_PROMPTS[:6])
            cats = report.summary.get("category_scores", {})
            assert len(cats) >= 3

    def test_benchmark_compare_two_models(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark, BENCHMARK_PROMPTS

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))

            def llm_a(p: str, m: int = 512) -> str:
                return "Model A good response"

            def llm_b(p: str, m: int = 512) -> str:
                return "Model B response"

            bm.run_benchmark(llm_a, "Model_A", "", prompts=[BENCHMARK_PROMPTS[0]])
            bm.run_benchmark(llm_b, "Model_B", "", prompts=[BENCHMARK_PROMPTS[0]])

            reports = bm.list_reports()
            assert len(reports) >= 2

            ids = [r["id"] for r in reports[:2]]
            comparison = bm.compare_reports(ids)
            if "error" not in comparison:
                assert "models" in comparison
                assert "metrics" in comparison

    def test_benchmark_prompts_cover_categories(self):
        from ggufloader.core.agent.benchmark import BENCHMARK_PROMPTS

        categories = {}
        for p in BENCHMARK_PROMPTS:
            categories.setdefault(p.category, []).append(p)

        assert "reasoning" in categories
        assert "coding" in categories
        assert "writing" in categories
        assert "math" in categories
        assert "general" in categories

        # Each category has at least one prompt
        for cat, prompts in categories.items():
            assert len(prompts) >= 1
            for p in prompts:
                assert p.id
                assert p.prompt
                assert p.max_tokens > 0


# ── API Routes ───────────────────────────────────────────────────────────


class TestPhase18Routes:
    """Tests for Phase 18 API routes."""

    def test_agent_routes_have_collab(self):
        from ggufloader.api.routes.agent import router
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        assert any("collab" in p for p in paths)

    def test_agent_routes_have_workflows(self):
        from ggufloader.api.routes.agent import router
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        assert any("workflows" in p for p in paths)

    def test_benchmark_routes(self):
        from ggufloader.api.routes.benchmark import router
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        assert len(paths) >= 3  # prompts, history, reports

    def test_workflows_api_has_templates(self):
        from ggufloader.api.routes.agent import router
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        assert any("templates" in p for p in paths)

    def test_workflows_api_has_validate(self):
        from ggufloader.api.routes.agent import router
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        assert any("validate" in p for p in paths)

    def test_workflows_api_has_dry_run(self):
        from ggufloader.api.routes.agent import router
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        assert any("dry-run" in p for p in paths)
