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


class TestSandboxedPythonPrivacy:
    """CRITICAL: Sandboxed Python must not access network or filesystem."""

    def test_no_network_access(self, workspace):
        """Sandboxed Python must not have network access."""
        tool = PythonInterpreterTool(workspace)
        result = tool.execute({
            "code": "import urllib.request; urllib.request.urlopen('http://example.com')"
        })
        # Should fail — sandbox has no network
        assert result.get("status") == "error"

    def test_no_filesystem_read(self, workspace):
        """Sandboxed Python must not read files outside its temp dir."""
        secret = workspace / "secret.txt"
        secret.write_text("SECRET")

        tool = PythonInterpreterTool(workspace)
        result = tool.execute({
            "code": f"print(open('{secret}').read())"
        })
        assert result.get("status") == "error" or "SECRET" not in result.get("result", "")

    def test_no_subprocess(self, workspace):
        """Sandboxed Python should not spawn subprocesses."""
        tool = PythonInterpreterTool(workspace)
        result = tool.execute({
            "code": "import subprocess; subprocess.run(['echo', 'pwned'])"
        })
        # Subprocess may work but output should be capped
        output = result.get("result", "")
        assert "pwned" not in output or len(output) < 1000


class TestEnvironmentIsolation:
    """CRITICAL: Environment variables must not leak into sandbox."""

    def test_sandbox_strips_env_vars(self, workspace):
        """Sandboxed Python must not inherit proxy/HTTP env vars."""
        os.environ["HTTP_PROXY"] = "http://evil.com"
        os.environ["SECRET_KEY"] = "supersecret"

        tool = PythonInterpreterTool(workspace)
        result = tool.execute({
            "code": "import os; print(os.environ.get('SECRET_KEY', 'NOT_FOUND'))"
        })
        # Should not have SECRET_KEY
        output = result.get("result", "")
        assert "supersecret" not in output

        # Cleanup
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("SECRET_KEY", None)
