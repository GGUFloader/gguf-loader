"""CRITICAL Gate: Agent Safety — 100% pass rate required.

Tests that agent tools cannot escape the workspace, that approval-gated
tools check requires_approval(), and that no tool can execute without
consent. A single failure BLOCKS deployment.

Equivalent to: CDSS Accuracy in healthcare eval harness.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from ggufloader.core.agent.tool_registry import (
    ToolRegistry,
    RunCommandTool,
    RunPythonTool,
    GitTool,
    PythonInterpreterTool,
    validate_tool_call,
)


@pytest.fixture
def sandbox_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory(prefix="gguf_safety_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def registry(sandbox_workspace):
    """Create a ToolRegistry bound to the sandbox."""
    return ToolRegistry(sandbox_workspace)


class TestPathSandbox:
    """CRITICAL: No tool must escape the workspace directory."""

    def test_read_file_cannot_escape(self, registry):
        """read_file must refuse paths that escape workspace."""
        result = registry.execute("read_file", {"path": "../../../etc/passwd"})
        assert result["status"] == "error"

    def test_write_file_cannot_escape(self, registry):
        """write_file must refuse paths that escape workspace."""
        result = registry.execute("write_file", {
            "path": "../../../tmp/evil.txt",
            "content": "pwned"
        })
        assert result["status"] == "error"

    def test_edit_file_cannot_escape(self, registry):
        """edit_file must refuse paths that escape workspace."""
        result = registry.execute("edit_file", {
            "path": "../../../etc/hostname",
            "operation": "replace",
            "find": "x",
            "replace": "y"
        })
        assert result["status"] == "error"

    def test_list_directory_cannot_escape(self, registry):
        """list_directory must refuse paths that escape workspace."""
        result = registry.execute("list_directory", {"path": "../../../"})
        assert result["status"] == "error"

    def test_search_files_cannot_escape(self, registry):
        """search_files must refuse paths that escape workspace."""
        result = registry.execute("search_files", {
            "pattern": "secret",
            "path": "../../../"
        })
        assert result["status"] == "error"

    def test_path_with_dotdot_segments(self, registry):
        """Paths with .. segments that resolve outside workspace are blocked."""
        result = registry.execute("read_file", {"path": "subdir/../../etc/passwd"})
        assert result["status"] == "error"

    def test_symlink_escape_attempt(self, registry, sandbox_workspace):
        """Symlinks pointing outside workspace should not allow reads."""
        # Create a symlink pointing outside
        link = sandbox_workspace / "evil_link"
        try:
            link.symlink_to("/etc/passwd")
            result = registry.execute("read_file", {"path": "evil_link"})
            # Should either fail or return error
            assert result["status"] == "error"
        except OSError:
            pass  # Symlink creation failed (e.g., Windows) — test passes


class TestApprovalGating:
    """CRITICAL: Dangerous tools must require approval."""

    def test_run_command_requires_approval(self, registry):
        """run_command must declare requires_approval=True."""
        tool = registry._tools.get("run_command")
        assert tool is not None
        assert tool.requires_approval({"command": "echo hello"}) is True

    def test_run_python_requires_approval(self, registry):
        """run_python must declare requires_approval=True."""
        tool = registry._tools.get("run_python")
        assert tool is not None
        assert tool.requires_approval({"code": "print(1)"}) is True

    def test_git_write_requires_approval(self, registry):
        """git write operations must require approval."""
        tool = registry._tools.get("git")
        assert tool is not None
        assert tool.requires_approval({"args": ["commit", "-m", "msg"]}) is True
        assert tool.requires_approval({"args": ["add", "."]}) is True
        assert tool.requires_approval({"args": ["push"]}) is True

    def test_git_read_no_approval(self, registry):
        """git read operations must NOT require approval."""
        tool = registry._tools.get("git")
        assert tool is not None
        assert tool.requires_approval({"args": ["status"]}) is False
        assert tool.requires_approval({"args": ["log"]}) is False
        assert tool.requires_approval({"args": ["diff"]}) is False

    def test_read_file_no_approval(self, registry):
        """read_file must NOT require approval."""
        tool = registry._tools.get("read_file")
        assert tool is not None
        assert tool.requires_approval({"path": "test.txt"}) is False

    def test_python_interpreter_no_approval(self, registry):
        """python_interpreter (sandboxed) must NOT require approval."""
        tool = registry._tools.get("python_interpreter")
        assert tool is not None
        assert tool.requires_approval({"code": "print(1)"}) is False

    def test_validate_tool_call_rejects_unknown(self, registry):
        """validate_tool_call must reject unknown tool names."""
        error = validate_tool_call(
            {"tool": "nonexistent_tool", "parameters": {}},
            registry
        )
        assert error is not None
        assert "Unknown tool" in error

    def test_validate_tool_call_rejects_missing_params(self, registry):
        """validate_tool_call must reject missing required parameters."""
        error = validate_tool_call(
            {"tool": "read_file", "parameters": {}},
            registry
        )
        assert error is not None
        assert "Missing required" in error


class TestSandboxedPython:
    """CRITICAL: PythonInterpreterTool must be safe by construction."""

    def test_sandbox_runs_in_temp_dir(self, sandbox_workspace):
        """Sandboxed Python must not have access to workspace."""
        tool = PythonInterpreterTool(sandbox_workspace)
        result = tool.execute({"code": "import os; print(os.getcwd())"})
        # The cwd should be a temp dir, NOT the workspace
        if result.get("status") == "success":
            cwd = result.get("result", "").strip()
            assert str(sandbox_workspace) not in cwd

    def test_sandbox_no_file_access(self, sandbox_workspace):
        """Sandboxed Python must not read workspace files."""
        # Create a file in workspace
        secret = sandbox_workspace / "secret.txt"
        secret.write_text("SECRET DATA")

        tool = PythonInterpreterTool(sandbox_workspace)
        result = tool.execute({
            "code": f"print(open('{secret}').read())"
        })
        # Should fail — sandbox has no access to workspace
        assert result.get("status") == "error" or "SECRET" not in result.get("result", "")

    def test_sandbox_output_capped(self, sandbox_workspace):
        """Sandboxed Python output must be capped at MAX_OUTPUT."""
        tool = PythonInterpreterTool(sandbox_workspace)
        result = tool.execute({
            "code": "print('A' * 100000)"
        })
        output = result.get("result", "")
        assert len(output) <= tool.MAX_OUTPUT + 100  # some overhead for status
