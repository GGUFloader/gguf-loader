"""Tests for Phase 17: Workflow Builder, Collaboration, Model Benchmark."""

from __future__ import annotations

import tempfile
import time
import json
from pathlib import Path

import pytest


# ── Workflow Builder ──────────────────────────────────────────────────────


class TestWorkflowBuilder:
    """Tests for the workflow builder backend."""

    def test_imports(self):
        from ggufloader.core.agent.workflow_builder import (
            WorkflowBuilder,
            Workflow,
            WorkflowStep,
        )

    def test_workflow_step_to_dict(self):
        from ggufloader.core.agent.workflow_builder import WorkflowStep

        step = WorkflowStep(id="s1", type="llm", name="Test Step",
                            config={"prompt": "hello"}, depends_on=["s0"])
        d = step.to_dict()
        assert d["id"] == "s1"
        assert d["type"] == "llm"
        assert d["depends_on"] == ["s0"]

    def test_workflow_step_from_dict(self):
        from ggufloader.core.agent.workflow_builder import WorkflowStep

        data = {"id": "s2", "type": "tool", "name": "Tool Step",
                "config": {"tool": "read_file"}, "depends_on": [], "outputs": ["content"]}
        step = WorkflowStep.from_dict(data)
        assert step.id == "s2"
        assert step.type == "tool"
        assert step.outputs == ["content"]

    def test_workflow_to_dict(self):
        from ggufloader.core.agent.workflow_builder import Workflow, WorkflowStep

        wf = Workflow(id="wf1", name="Test WF", description="desc",
                      steps=[WorkflowStep(id="s1", type="llm", name="S1")])
        d = wf.to_dict()
        assert d["name"] == "Test WF"
        assert len(d["steps"]) == 1

    def test_workflow_validate_no_errors(self):
        from ggufloader.core.agent.workflow_builder import Workflow, WorkflowStep

        wf = Workflow(id="wf1", name="Test", description="",
                      steps=[
                          WorkflowStep(id="s1", type="llm", name="S1"),
                          WorkflowStep(id="s2", type="tool", name="S2", depends_on=["s1"]),
                      ])
        errors = wf.validate()
        assert len(errors) == 0

    def test_workflow_validate_bad_dependency(self):
        from ggufloader.core.agent.workflow_builder import Workflow, WorkflowStep

        wf = Workflow(id="wf1", name="Test", description="",
                      steps=[
                          WorkflowStep(id="s1", type="llm", name="S1", depends_on=["nonexistent"]),
                      ])
        errors = wf.validate()
        assert len(errors) >= 1
        assert "nonexistent" in errors[0]

    def test_workflow_validate_cycle(self):
        from ggufloader.core.agent.workflow_builder import Workflow, WorkflowStep

        wf = Workflow(id="wf1", name="Test", description="",
                      steps=[
                          WorkflowStep(id="a", type="llm", name="A", depends_on=["b"]),
                          WorkflowStep(id="b", type="llm", name="B", depends_on=["a"]),
                      ])
        errors = wf.validate()
        assert any("cycle" in e.lower() for e in errors)

    def test_workflow_execution_order(self):
        from ggufloader.core.agent.workflow_builder import Workflow, WorkflowStep

        wf = Workflow(id="wf1", name="Test", description="",
                      steps=[
                          WorkflowStep(id="s1", type="llm", name="S1"),
                          WorkflowStep(id="s2", type="tool", name="S2", depends_on=["s1"]),
                          WorkflowStep(id="s3", type="llm", name="S3", depends_on=["s2"]),
                      ])
        order = wf.execution_order()
        assert order.index("s1") < order.index("s2") < order.index("s3")

    def test_create_from_template(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder

        with tempfile.TemporaryDirectory() as td:
            wb = WorkflowBuilder(Path(td) / "workflows")
            wf = wb.create_from_template("code_review", "My Review")
            assert wf is not None
            assert wf.name == "My Review"
            assert len(wf.steps) >= 3

    def test_list_all(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder

        with tempfile.TemporaryDirectory() as td:
            wb = WorkflowBuilder(Path(td) / "workflows")
            wb.create_from_template("code_review", "R1")
            wb.create_from_template("refactor", "R2")
            all_wf = wb.list_all()
            assert len(all_wf) >= 2

    def test_get_workflow(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder

        with tempfile.TemporaryDirectory() as td:
            wb = WorkflowBuilder(Path(td) / "workflows")
            wf = wb.create_from_template("code_review")
            got = wb.get(wf.id)
            assert got is not None
            assert got.id == wf.id

    def test_delete_workflow(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder

        with tempfile.TemporaryDirectory() as td:
            wb = WorkflowBuilder(Path(td) / "workflows")
            wf = wb.create_from_template("code_review")
            deleted = wb.delete(wf.id)
            assert deleted is True
            assert wb.get(wf.id) is None

    def test_duplicate_workflow(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder

        with tempfile.TemporaryDirectory() as td:
            wb = WorkflowBuilder(Path(td) / "workflows")
            wf = wb.create_from_template("code_review")
            dup = wb.duplicate(wf.id, "Dup Review")
            assert dup is not None
            assert dup.name == "Dup Review"
            assert dup.id != wf.id
            assert len(dup.steps) == len(wf.steps)

    def test_dry_run(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder

        with tempfile.TemporaryDirectory() as td:
            wb = WorkflowBuilder(Path(td) / "workflows")
            wf = wb.create_from_template("code_review")
            result = wb.execute_dry_run(wf.id)
            assert result["valid"] is True
            assert result["step_count"] >= 3

    def test_list_templates(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder

        wb = WorkflowBuilder()
        templates = wb.list_templates()
        assert len(templates) >= 3
        names = [t["name"] for t in templates]
        assert "Code Review Pipeline" in names

    def test_persist_workflows(self):
        from ggufloader.core.agent.workflow_builder import WorkflowBuilder

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "workflows"
            wb1 = WorkflowBuilder(path)
            wf = wb1.create_from_template("code_review", "Persist Me")

            # Reload from disk
            wb2 = WorkflowBuilder(path)
            assert wb2.get(wf.id) is not None


# ── Collaboration ─────────────────────────────────────────────────────────


class TestCollaboration:
    """Tests for the collaboration backend."""

    def test_imports(self):
        from ggufloader.core.agent.collaboration import (
            CollaborationManager,
            Collaborator,
            CollaborativeSession,
            get_collab_manager,
        )

    def test_join_session(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        collab = mgr.join_session("sess1", "user1", "Alice")
        assert collab.name == "Alice"
        assert collab.id == "user1"
        assert collab.color.startswith("#")

    def test_leave_session(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("sess1", "user1", "Alice")
        mgr.leave_session("sess1", "user1")
        info = mgr.get_session_info("sess1")
        assert len(info["collaborators"]) == 0

    def test_multiple_collaborators(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("sess1", "u1", "Alice")
        mgr.join_session("sess1", "u2", "Bob")
        info = mgr.get_session_info("sess1")
        assert info["collaborator_count"] == 2

    def test_update_cursor(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("sess1", "u1", "Alice")
        mgr.update_cursor("sess1", "u1", {"line": 10, "col": 5})
        info = mgr.get_session_info("sess1")
        alice = [c for c in info["collaborators"] if c["id"] == "u1"][0]
        assert alice["cursor_position"]["line"] == 10

    def test_set_typing(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("sess1", "u1", "Alice")
        mgr.set_typing("sess1", "u1", True)
        info = mgr.get_session_info("sess1")
        alice = [c for c in info["collaborators"] if c["id"] == "u1"][0]
        assert alice["is_typing"] is True

    def test_broadcast_event(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("sess1", "u1", "Alice")
        mgr.join_session("sess1", "u2", "Bob")
        targets = mgr.broadcast_event("sess1", {"type": "edit"}, exclude_user="u1")
        assert "u2" in targets
        assert "u1" not in targets

    def test_active_sessions(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("s1", "u1", "A")
        mgr.join_session("s2", "u2", "B")
        active = mgr.get_active_sessions()
        assert len(active) == 2

    def test_cleanup_stale(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        collab = mgr.join_session("s1", "u1", "Alice")
        collab.last_active = time.time() - 600  # 10 minutes ago
        removed = mgr.cleanup_stale(timeout=300)
        assert removed == 1

    def test_get_user_sessions(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        mgr.join_session("s1", "u1", "Alice")
        mgr.join_session("s2", "u1", "Alice")
        sessions = mgr.get_user_sessions("u1")
        assert len(sessions) == 2

    def test_generate_user_id(self):
        from ggufloader.core.agent.collaboration import CollaborationManager

        mgr = CollaborationManager()
        uid = mgr.generate_user_id()
        assert uid.startswith("user_")

    def test_singleton(self):
        from ggufloader.core.agent.collaboration import get_collab_manager

        mgr1 = get_collab_manager()
        mgr2 = get_collab_manager()
        assert mgr1 is mgr2


# ── Model Benchmark ──────────────────────────────────────────────────────


class TestModelBenchmark:
    """Tests for the model benchmark backend."""

    def test_imports(self):
        from ggufloader.core.agent.benchmark import (
            ModelBenchmark,
            BenchmarkPrompt,
            BenchmarkPerformanceResult,
            BenchmarkReport,
            BENCHMARK_PROMPTS,
        )

    def test_benchmark_prompts_defined(self):
        from ggufloader.core.agent.benchmark import BENCHMARK_PROMPTS

        assert len(BENCHMARK_PROMPTS) >= 5
        categories = {p.category for p in BENCHMARK_PROMPTS}
        assert "reasoning" in categories
        assert "coding" in categories

    def test_list_prompts(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))
            prompts = bm.list_prompts()
            assert len(prompts) >= 5

    def test_run_benchmark(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark, BENCHMARK_PROMPTS

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))

            def mock_llm(prompt: str, max_tokens: int = 512) -> str:
                return f"Response to: {prompt[:30]}..."

            report = bm.run_benchmark(mock_llm, "test_model", "/fake/model.gguf",
                                       prompts=BENCHMARK_PROMPTS[:3])
            assert report.model_name == "test_model"
            assert len(report.results) == 3
            assert report.summary["prompt_count"] == 3
            assert report.summary["avg_tps"] > 0

    def test_get_history(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark, BENCHMARK_PROMPTS

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))

            def mock_llm(p: str, m: int = 512) -> str:
                return "ok"

            bm.run_benchmark(mock_llm, "m1", "", prompts=[BENCHMARK_PROMPTS[0]])
            history = bm.get_history()
            assert len(history) >= 1

    def test_compare_reports(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark, BENCHMARK_PROMPTS

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))

            def mock_llm(p: str, m: int = 512) -> str:
                return "test response"

            bm.run_benchmark(mock_llm, "model_a", "", prompts=[BENCHMARK_PROMPTS[0]])
            bm.run_benchmark(mock_llm, "model_b", "", prompts=[BENCHMARK_PROMPTS[0]])

            reports = bm.list_reports()
            assert len(reports) >= 2

            ids = [r["id"] for r in reports[:2]]
            comparison = bm.compare_reports(ids)
            assert "models" in comparison or "error" in comparison

    def test_list_reports(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark, BENCHMARK_PROMPTS

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))

            def mock_llm(p: str, m: int = 512) -> str:
                return "ok"

            bm.run_benchmark(mock_llm, "m", "", prompts=[BENCHMARK_PROMPTS[0]])
            reports = bm.list_reports()
            assert len(reports) >= 1

    def test_report_to_dict(self):
        from ggufloader.core.agent.benchmark import BenchmarkReport, BenchmarkPerformanceResult

        result = BenchmarkPerformanceResult(
            prompt_id="test", category="general", response="hello",
            tokens_generated=10, generation_time_ms=100.0,
            first_token_ms=15.0, tokens_per_second=100.0,
            keyword_score=0.8, quality_score=0.7,
        )
        report = BenchmarkReport(
            model_name="test", model_path="/fake",
            timestamp=time.time(), results=[result],
            summary={"avg_tps": 100},
        )
        d = report.to_dict()
        assert d["model_name"] == "test"
        assert d["result_count"] == 1
        assert d["summary"]["avg_tps"] == 100

    def test_get_report(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark, BENCHMARK_PROMPTS

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))

            def mock_llm(p: str, m: int = 512) -> str:
                return "ok"

            bm.run_benchmark(mock_llm, "m", "", prompts=[BENCHMARK_PROMPTS[0]])
            reports = bm.list_reports()
            report = bm.get_report(reports[0]["id"])
            assert report is not None
            assert report["model_name"] == "m"


# ── API Route imports ────────────────────────────────────────────────────


class TestPhase17Routes:
    """Tests that Phase 17 API routes can be imported."""

    def test_benchmark_routes_import(self):
        from ggufloader.api.routes.benchmark import router
        assert router is not None

    def test_workflow_routes_exist(self):
        from ggufloader.api.routes.workflows import router
        assert router is not None

    def test_workflows_in_agent_routes(self):
        from ggufloader.api.routes.agent import router
        routes = [r.path for r in router.routes if hasattr(r, 'path')]
        assert any("workflows" in r for r in routes)

    def test_collab_in_agent_routes(self):
        from ggufloader.api.routes.agent import router
        routes = [r.path for r in router.routes if hasattr(r, 'path')]
        assert any("collab" in r for r in routes)

    def test_benchmark_router_registered(self):
        from ggufloader.api.app import create_app
        app = create_app()
        routes = [str(getattr(r, 'path', r)) for r in app.routes]
        assert any("benchmark" in r for r in routes)

    def test_search_router_registered(self):
        from ggufloader.api.app import create_app
        app = create_app()
        routes = [str(getattr(r, 'path', r)) for r in app.routes]
        assert any("search" in r for r in routes)


# ── Benchmark module merge (original + new) ──────────────────────────────


class TestBenchmarkSuiteMerge:
    """Test that original BenchmarkSuite and new ModelBenchmark coexist."""

    def test_benchmark_suite_still_works(self):
        from ggufloader.core.agent.benchmark import BenchmarkSuite, BenchmarkTask

        def agent_fn(prompt: str) -> dict:
            return {"response": "I can do that", "tool_results": []}

        suite = BenchmarkSuite(agent_fn)
        task = BenchmarkTask(
            id="test1", name="Test", description="Test task",
            prompt="Do something", criteria=["No errors"],
        )
        suite.add_task(task)
        report = suite.run_all()
        assert report["summary"]["total"] == 1

    def test_model_benchmark_still_works(self):
        from ggufloader.core.agent.benchmark import ModelBenchmark, BENCHMARK_PROMPTS

        with tempfile.TemporaryDirectory() as td:
            bm = ModelBenchmark(Path(td))

            def llm(prompt: str, max_tokens: int = 512) -> str:
                return "I am a language model"

            report = bm.run_benchmark(llm, "coexist_test", "", prompts=[BENCHMARK_PROMPTS[0]])
            assert report.summary["avg_tps"] > 0
