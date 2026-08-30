"""Tests for Phase 9: Model catalog and frontend panel wiring."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Model catalog endpoint
# ---------------------------------------------------------------------------

class TestModelCatalog:
    """Tests for GET /api/model/catalog."""

    def test_catalog_imports(self):
        from ggufloader.api.routes.model import model_catalog

    def test_catalog_nonexistent_directory(self):
        from ggufloader.api.routes.model import model_catalog

        result = __import__("asyncio").get_event_loop().run_until_complete(
            model_catalog(directory="/nonexistent/path/that/does/not/exist")
        )
        assert result["models"] == []
        assert "error" in result

    def test_catalog_empty_directory(self):
        from ggufloader.api.routes.model import model_catalog

        with tempfile.TemporaryDirectory() as tmp:
            result = __import__("asyncio").get_event_loop().run_until_complete(
                model_catalog(directory=tmp)
            )
            assert result["count"] == 0
            assert result["models"] == []
            assert result["directory"] == tmp

    def test_catalog_with_fake_gguf(self):
        """Catalog should find .gguf files but fail gracefully on invalid metadata."""
        from ggufloader.api.routes.model import model_catalog

        with tempfile.TemporaryDirectory() as tmp:
            # Create a fake .gguf file
            fake = Path(tmp) / "test-model-Q4_K_M.gguf"
            fake.write_bytes(b"\x00" * 1024)  # minimal content

            result = __import__("asyncio").get_event_loop().run_until_complete(
                model_catalog(directory=tmp)
            )
            assert result["count"] == 1
            model = result["models"][0]
            assert model["filename"] == "test-model-Q4_K_M.gguf"
            assert model["size_gb"] == 0.0  # very small file
            assert model["path"] == str(fake)

    def test_catalog_recursive(self):
        """Catalog should find .gguf files in subdirectories when recursive=True."""
        from ggufloader.api.routes.model import model_catalog

        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / "subdir"
            sub.mkdir()
            (sub / "nested.gguf").write_bytes(b"\x00" * 512)

            result = __import__("asyncio").get_event_loop().run_until_complete(
                model_catalog(directory=tmp, recursive=True)
            )
            assert result["count"] == 1
            assert result["models"][0]["filename"] == "nested.gguf"

    def test_catalog_non_recursive(self):
        """Catalog should NOT find .gguf in subdirs when recursive=False."""
        from ggufloader.api.routes.model import model_catalog

        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / "subdir"
            sub.mkdir()
            (sub / "nested.gguf").write_bytes(b"\x00" * 512)

            result = __import__("asyncio").get_event_loop().run_until_complete(
                model_catalog(directory=tmp, recursive=False)
            )
            assert result["count"] == 0

    def test_catalog_multiple_models(self):
        from ggufloader.api.routes.model import model_catalog

        with tempfile.TemporaryDirectory() as tmp:
            for name in ["model_a.gguf", "model_b.gguf", "model_c.bin"]:
                (Path(tmp) / name).write_bytes(b"\x00" * 100)

            result = __import__("asyncio").get_event_loop().run_until_complete(
                model_catalog(directory=tmp)
            )
            assert result["count"] == 2  # only .gguf files
            filenames = {m["filename"] for m in result["models"]}
            assert "model_a.gguf" in filenames
            assert "model_b.gguf" in filenames
            assert "model_c.bin" not in filenames


# ---------------------------------------------------------------------------
# Profiling API endpoints
# ---------------------------------------------------------------------------

class TestProfilingEndpoints:
    """Tests for the profiling API endpoints."""

    def test_profile_history_imports(self):
        from ggufloader.api.routes.agent import profile_history, profile_steps, profile_bottlenecks, profile_throughput

    def test_profile_history_returns_list(self):
        from ggufloader.api.routes.agent import profile_history
        result = __import__("asyncio").get_event_loop().run_until_complete(profile_history())
        assert isinstance(result, list)

    def test_profile_bottlenecks_returns_dict(self):
        from ggufloader.api.routes.agent import profile_bottlenecks
        result = __import__("asyncio").get_event_loop().run_until_complete(profile_bottlenecks())
        assert isinstance(result, dict)
        assert "bottlenecks" in result
        assert "suggestions" in result

    def test_profile_throughput_returns_list(self):
        from ggufloader.api.routes.agent import profile_throughput
        result = __import__("asyncio").get_event_loop().run_until_complete(profile_throughput())
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# MCP and hot-swap API endpoints
# ---------------------------------------------------------------------------

class TestMCPAndHotSwapEndpoints:
    """Tests for the MCP and model hot-swap endpoints."""

    def test_mcp_endpoints_imports(self):
        from ggufloader.api.routes.agent import agent_mcp_servers, agent_mcp_tools

    def test_mcp_servers_returns_list(self):
        from ggufloader.api.routes.agent import agent_mcp_servers
        result = __import__("asyncio").get_event_loop().run_until_complete(agent_mcp_servers())
        assert isinstance(result, list)

    def test_mcp_tools_returns_list(self):
        from ggufloader.api.routes.agent import agent_mcp_tools
        result = __import__("asyncio").get_event_loop().run_until_complete(agent_mcp_tools())
        assert isinstance(result, list)

    def test_model_status_endpoint(self):
        from ggufloader.api.routes.agent import agent_model_status
        result = __import__("asyncio").get_event_loop().run_until_complete(agent_model_status())
        assert "loaded" in result
