"""Tests for Phase 11: Prompt Templates, Session Branching, and Diff Viewer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

class TestPromptTemplates:
    """Tests for the template system."""

    def test_import(self):
        from ggufloader.core.agent.templates import TemplateManager, PromptTemplate, BUILTIN_TEMPLATES

    def test_builtin_templates_exist(self):
        from ggufloader.core.agent.templates import BUILTIN_TEMPLATES
        assert len(BUILTIN_TEMPLATES) >= 8
        ids = {t["id"] for t in BUILTIN_TEMPLATES}
        assert "code_review" in ids
        assert "debug_error" in ids

    def test_template_render(self):
        from ggufloader.core.agent.templates import PromptTemplate

        t = PromptTemplate(
            template_id="test", name="Test", description="",
            template="Hello {{name}}, your code:\n{{code}}",
            variables=["name", "code"],
        )
        result = t.render(name="Alice", code="print('hi')")
        assert "Hello Alice" in result
        assert "print('hi')" in result

    def test_missing_variables(self):
        from ggufloader.core.agent.templates import PromptTemplate

        t = PromptTemplate(
            template_id="test", name="Test", description="",
            template="{{a}} and {{b}}",
            variables=["a", "b"],
        )
        missing = t.missing_variables(a="1")
        assert missing == ["b"]

    def test_manager_list_all(self):
        from ggufloader.core.agent.templates import TemplateManager

        with tempfile.TemporaryDirectory() as tmp:
            mgr = TemplateManager(Path(tmp))
            all_t = mgr.list_all()
            assert len(all_t) >= 8

    def test_manager_get_by_id(self):
        from ggufloader.core.agent.templates import TemplateManager

        with tempfile.TemporaryDirectory() as tmp:
            mgr = TemplateManager(Path(tmp))
            t = mgr.get("code_review")
            assert t is not None
            assert t.name == "Code Review"

    def test_manager_search(self):
        from ggufloader.core.agent.templates import TemplateManager

        with tempfile.TemporaryDirectory() as tmp:
            mgr = TemplateManager(Path(tmp))
            results = mgr.search("debug")
            assert len(results) >= 1
            assert any("debug" in t.name.lower() or "debug" in t.description.lower() for t in results)

    def test_manager_categories(self):
        from ggufloader.core.agent.templates import TemplateManager

        with tempfile.TemporaryDirectory() as tmp:
            mgr = TemplateManager(Path(tmp))
            cats = mgr.get_categories()
            assert len(cats) >= 3
            cat_names = {c["name"] for c in cats}
            assert "development" in cat_names

    def test_save_and_load_custom(self):
        from ggufloader.core.agent.templates import TemplateManager, PromptTemplate

        with tempfile.TemporaryDirectory() as tmp:
            mgr = TemplateManager(Path(tmp))
            t = PromptTemplate(
                template_id="custom_test", name="Custom", description="A custom template",
                template="Do {{thing}}", variables=["thing"],
                category="custom",
            )
            mgr.save(t)

            # Reload from disk
            mgr2 = TemplateManager(Path(tmp))
            loaded = mgr2.get("custom_test")
            assert loaded is not None
            assert loaded.name == "Custom"

    def test_delete_custom_template(self):
        from ggufloader.core.agent.templates import TemplateManager, PromptTemplate

        with tempfile.TemporaryDirectory() as tmp:
            mgr = TemplateManager(Path(tmp))
            t = PromptTemplate(
                template_id="to_delete", name="Delete Me", description="",
                template="test", variables=[],
            )
            mgr.save(t)
            assert mgr.delete("to_delete") is True
            assert mgr.get("to_delete") is None

    def test_cannot_delete_builtin(self):
        from ggufloader.core.agent.templates import TemplateManager

        with tempfile.TemporaryDirectory() as tmp:
            mgr = TemplateManager(Path(tmp))
            assert mgr.delete("code_review") is False

    def test_compose_templates(self):
        from ggufloader.core.agent.templates import TemplateManager

        with tempfile.TemporaryDirectory() as tmp:
            mgr = TemplateManager(Path(tmp))
            result = mgr.compose(["explain_code", "code_review"], code="test code")
            assert "Explain" in result
            assert "Review" in result
            assert "test code" in result


# ---------------------------------------------------------------------------
# Session Branching
# ---------------------------------------------------------------------------

class TestSessionBranching:
    """Tests for session branching and timeline."""

    def test_import(self):
        from ggufloader.core.agent.branching import SessionBranching, Branch, Message

    def test_create_session(self):
        from ggufloader.core.agent.branching import SessionBranching

        with tempfile.TemporaryDirectory() as tmp:
            sb = SessionBranching(Path(tmp))
            branch = sb.create_session("test_session")
            assert branch.name == "main"
            assert sb.active_branch is not None

    def test_add_messages(self):
        from ggufloader.core.agent.branching import SessionBranching

        with tempfile.TemporaryDirectory() as tmp:
            sb = SessionBranching(Path(tmp))
            sb.create_session("test")
            msg1 = sb.add_message("user", "Hello")
            msg2 = sb.add_message("assistant", "Hi there")
            assert msg1 is not None
            assert msg2 is not None
            assert sb.active_branch.length == 2

    def test_fork_branch(self):
        from ggufloader.core.agent.branching import SessionBranching

        with tempfile.TemporaryDirectory() as tmp:
            sb = SessionBranching(Path(tmp))
            branch = sb.create_session("test")
            sb.add_message("user", "msg1")
            sb.add_message("assistant", "msg2")
            sb.add_message("user", "msg3")

            forked = sb.fork(branch.id, 2, "experiment")
            assert forked is not None
            assert forked.fork_point == 2
            assert forked.length == 2  # fork_point messages copied

    def test_switch_branch(self):
        from ggufloader.core.agent.branching import SessionBranching

        with tempfile.TemporaryDirectory() as tmp:
            sb = SessionBranching(Path(tmp))
            branch = sb.create_session("test")
            sb.add_message("user", "hello")

            forked = sb.fork(branch.id, 1, "new_branch")
            assert forked is not None
            assert sb.switch_branch(forked.id)
            assert sb.active_branch.id == forked.id

    def test_merge_branches(self):
        from ggufloader.core.agent.branching import SessionBranching

        with tempfile.TemporaryDirectory() as tmp:
            sb = SessionBranching(Path(tmp))
            branch = sb.create_session("test")
            sb.add_message("user", "msg1")

            forked = sb.fork(branch.id, 1, "fork")
            sb.switch_branch(forked.id)
            sb.add_message("assistant", "fork_reply")

            assert sb.merge(forked.id, branch.id)
            sb.switch_branch(branch.id)
            assert sb.active_branch.length == 2  # original + fork's message

    def test_diff_branches(self):
        from ggufloader.core.agent.branching import SessionBranching

        with tempfile.TemporaryDirectory() as tmp:
            sb = SessionBranching(Path(tmp))
            branch = sb.create_session("test")
            sb.add_message("user", "msg1")

            forked = sb.fork(branch.id, 1, "fork")
            sb.switch_branch(forked.id)
            sb.add_message("assistant", "different_reply")

            diff = sb.diff_branches(branch.id, forked.id)
            assert diff["common_prefix"] == 1
            assert diff["b_only_count"] == 1

    def test_timeline(self):
        from ggufloader.core.agent.branching import SessionBranching

        with tempfile.TemporaryDirectory() as tmp:
            sb = SessionBranching(Path(tmp))
            branch = sb.create_session("test")
            sb.add_message("user", "hello")

            forked = sb.fork(branch.id, 1, "exp")
            timeline = sb.get_timeline()
            assert len(timeline) == 2
            assert any(t["name"] == "main" for t in timeline)
            assert any(t["name"] == "exp" for t in timeline)

    def test_save_and_load(self):
        from ggufloader.core.agent.branching import SessionBranching

        with tempfile.TemporaryDirectory() as tmp:
            sb = SessionBranching(Path(tmp))
            branch = sb.create_session("save_test")
            sb.add_message("user", "saved message")
            sb.save("save_test")

            sb2 = SessionBranching(Path(tmp))
            assert sb2.load("save_test")
            assert sb2.active_branch is not None
            assert sb2.active_branch.length == 1

    def test_list_branches(self):
        from ggufloader.core.agent.branching import SessionBranching

        with tempfile.TemporaryDirectory() as tmp:
            sb = SessionBranching(Path(tmp))
            branch = sb.create_session("test")
            forked = sb.fork(branch.id, 0, "exp")
            branches = sb.list_branches()
            assert len(branches) == 2


# ---------------------------------------------------------------------------
# Diff Viewer
# ---------------------------------------------------------------------------

class TestDiffViewer:
    """Tests for the diff computation and formatting."""

    def test_import(self):
        from ggufloader.core.agent.diff_viewer import compute_diff, compute_side_by_side, extract_diffs_from_tool_results

    def test_compute_diff(self):
        from ggufloader.core.agent.diff_viewer import compute_diff

        old = "line1\nline2\nline3"
        new = "line1\nmodified\nline3"
        result = compute_diff(old, new, "test.py")
        assert result["filename"] == "test.py"
        assert result["stats"]["additions"] >= 1
        assert result["stats"]["deletions"] >= 1
        assert len(result["hunks"]) >= 1

    def test_compute_diff_identical(self):
        from ggufloader.core.agent.diff_viewer import compute_diff

        text = "same text\nhere"
        result = compute_diff(text, text)
        assert result["stats"]["additions"] == 0
        assert result["stats"]["deletions"] == 0

    def test_compute_side_by_side(self):
        from ggufloader.core.agent.diff_viewer import compute_side_by_side

        old = "hello\nworld"
        new = "hello\nuniverse"
        result = compute_side_by_side(old, new, "test.txt")
        assert result["filename"] == "test.txt"
        assert len(result["lines"]) >= 2
        # Find the replace line
        replaces = [l for l in result["lines"] if l["type"] == "replace"]
        assert len(replaces) >= 1
        assert replaces[0]["old_text"] == "world"
        assert replaces[0]["new_text"] == "universe"

    def test_side_by_side_insert(self):
        from ggufloader.core.agent.diff_viewer import compute_side_by_side

        old = "line1"
        new = "line1\nline2"
        result = compute_side_by_side(old, new)
        inserts = [l for l in result["lines"] if l["type"] == "insert"]
        assert len(inserts) == 1
        assert inserts[0]["new_text"] == "line2"

    def test_side_by_side_delete(self):
        from ggufloader.core.agent.diff_viewer import compute_side_by_side

        old = "line1\nline2"
        new = "line1"
        result = compute_side_by_side(old, new)
        deletes = [l for l in result["lines"] if l["type"] == "delete"]
        assert len(deletes) == 1
        assert deletes[0]["old_text"] == "line2"

    def test_extract_diffs_from_results(self):
        from ggufloader.core.agent.diff_viewer import extract_diffs_from_tool_results

        results = [
            {"tool_name": "write_file", "status": "success", "path": "test.py", "content": "print('hello')"},
            {"tool_name": "edit_file", "status": "success", "path": "main.py", "operation": "replace", "changes_made": 3},
        ]
        diffs = extract_diffs_from_tool_results(results)
        assert len(diffs) == 2
        assert diffs[0]["type"] == "create"
        assert diffs[1]["type"] == "modify"

    def test_extract_diffs_empty(self):
        from ggufloader.core.agent.diff_viewer import extract_diffs_from_tool_results
        assert extract_diffs_from_tool_results([]) == []


# ---------------------------------------------------------------------------
# API endpoint imports
# ---------------------------------------------------------------------------

class TestPhase11Endpoints:
    """Tests for the new API endpoints."""

    def test_template_endpoints_import(self):
        from ggufloader.api.routes.templates import list_templates, create_template, render_template

    def test_branching_endpoints_import(self):
        from ggufloader.api.routes.branching import list_branches, fork_branch, diff_branches

    def test_template_list(self):
        from ggufloader.api.routes.templates import list_templates
        result = __import__("asyncio").get_event_loop().run_until_complete(list_templates())
        assert isinstance(result, list)
        assert len(result) >= 8

    def test_template_categories(self):
        from ggufloader.api.routes.templates import list_categories
        result = __import__("asyncio").get_event_loop().run_until_complete(list_categories())
        assert isinstance(result, list)
        assert len(result) >= 3

    def test_template_search(self):
        from ggufloader.api.routes.templates import search_templates
        result = __import__("asyncio").get_event_loop().run_until_complete(search_templates(q="debug"))
        assert isinstance(result, list)
        assert len(result) >= 1
