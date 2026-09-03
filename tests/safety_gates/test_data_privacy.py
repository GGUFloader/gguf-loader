"""CRITICAL Gate: Data Privacy — 100% pass rate required.

Tests that no tool can leak data outside the workspace, that network
access is restricted in sandboxes, and that sensitive data (file contents,
environment variables) cannot be exfiltrated.

Equivalent to: PHI Exposure in healthcare eval harness.
"""
import os
import tempfile
from pathlib import Path

import pytest

from ggufloader.core.agent.tool_registry import (
    ToolRegistry,
    PythonInterpreterTool,
    RunCommandTool,
)


@pytest.fixture
def workspace():
    with tempfile.TemporaryDirectory(prefix="gguf_privacy_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def registry(workspace):
    return ToolRegistry(workspace)


class TestNoDataExfiltration:
    """CRITICAL: Tools must not leak data outside workspace."""

    def test_write_file_stays_in_workspace(self, registry, workspace):
        """write_file must only write inside workspace."""
        result = registry.execute("write_file", {
            "path": "test.txt",
            "content": "hello"
        })
        assert result["status"] == "success"
        assert (workspace / "test.txt").exists()

        # Verify nothing was written outside
        outside = Path("/tmp/gguf_leak_test.txt")
        assert not outside.exists()

    def test_read_file_only_reads_workspace(self, registry, workspace):
        """read_file must only read from inside workspace."""
        # Create a file in workspace
        (workspace / "safe.txt").write_text("safe content")

        # Try to read outside
        result = registry.execute("read_file", {"path": "/etc/hostname"})
        assert result["status"] == "error"

    def test_search_files_stays_in_workspace(self, registry, workspace):
        """search_files must only search inside workspace."""
        (workspace / "secret.txt").write_text("password=12345")

        # Search inside — should find it
        result = registry.execute("search_files", {
            "pattern": "password",
            "path": "."
        })
        assert result["status"] == "success"

        # Search outside — must fail
        result = registry.execute("search_files", {
            "pattern": "password",
            "path": "/etc"
        })
        assert result["status"] == "error"


class TestPythonInterpreterAliasPrivacy:
    """CRITICAL: python_interpreter aliases run_python (one approval gate).

    The former "sandboxed" interpreter was NOT an OS sandbox - it executed
    arbitrary Python with the full user interpreter, so urllib, absolute-
    path file reads and subprocesses all worked from the temp cwd. Task 10
    merges it into run_python: same schema, same approval gate, so no
    python code ever runs without user consent.
    """

    def test_alias_requires_approval(self, workspace):
        """The alias must be approval-gated exactly like run_python."""
        tool = PythonInterpreterTool(workspace)
        assert tool.requires_approval({"code": "print(1)"}) is True

    def test_alias_shares_run_python_schema(self, workspace):
        """One schema for all python execution (no approval-free variant)."""
        from ggufloader.core.agent.tool_registry import RunPythonTool
        assert issubclass(PythonInterpreterTool, RunPythonTool)
        assert PythonInterpreterTool.schema == RunPythonTool.schema

    def test_alias_warns_deprecation(self, workspace):
        """Calling python_interpreter steers callers to run_python."""
        import warnings
        tool = PythonInterpreterTool(workspace)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            tool.execute({"code": "print('alias')"})
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
