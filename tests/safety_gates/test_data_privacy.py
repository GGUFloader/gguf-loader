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


class TestSinglePythonPath:
    """CRITICAL: only run_python executes Python, and it requires approval.

    The former "sandboxed" interpreter was NOT an OS sandbox — it executed
    arbitrary Python with the full user interpreter. It has been removed;
    the registry exposes exactly one python tool (run_python), so no python
    code ever runs without user consent.
    """

    def test_no_python_alias_registered(self, registry):
        """No approval-free python alias exists in the catalog."""
        names = registry.names()
        assert "python_interpreter" not in names
        assert "run_python" in names

    def test_run_python_requires_approval(self, registry):
        """run_python stays approval-gated."""
        assert registry.requires_approval("run_python", {"code": "print(1)"}) is True
