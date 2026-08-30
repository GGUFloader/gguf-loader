"""Tests for Phase 10: Plugin Marketplace and Model Comparison."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Plugin marketplace endpoints
# ---------------------------------------------------------------------------

class TestPluginMarketplace:
    """Tests for the enhanced plugin routes."""

    def test_catalog_imports(self):
        from ggufloader.api.routes.plugins import plugin_catalog, plugin_categories, list_plugins, plugin_stats

    def test_plugin_catalog_returns_list(self):
        from ggufloader.api.routes.plugins import plugin_catalog
        result = __import__("asyncio").get_event_loop().run_until_complete(plugin_catalog())
        assert isinstance(result, list)
        assert len(result) > 0  # should have built-in catalog items
        first = result[0]
        assert "id" in first
        assert "name" in first
        assert "description" in first
        assert "category" in first
        assert "installed" in first

    def test_plugin_catalog_filter_by_category(self):
        from ggufloader.api.routes.plugins import plugin_catalog
        result = __import__("asyncio").get_event_loop().run_until_complete(plugin_catalog(category="devops"))
        assert all(p["category"] == "devops" for p in result)
        assert len(result) >= 2  # docker, git-advanced, testing

    def test_plugin_categories(self):
        from ggufloader.api.routes.plugins import plugin_categories
        result = __import__("asyncio").get_event_loop().run_until_complete(plugin_categories())
        assert isinstance(result, list)
        assert len(result) > 0
        cats = {c["name"] for c in result}
        assert "devops" in cats

    def test_plugin_stats(self):
        from ggufloader.api.routes.plugins import plugin_stats
        result = __import__("asyncio").get_event_loop().run_until_complete(plugin_stats())
        assert "total" in result
        assert "loaded" in result
        assert "discovered" in result

    def test_list_plugins_returns_list(self):
        from ggufloader.api.routes.plugins import list_plugins
        result = __import__("asyncio").get_event_loop().run_until_complete(list_plugins())
        assert isinstance(result, list)

    def test_builtin_catalog_has_all_categories(self):
        from ggufloader.api.routes.plugins import _BUILTIN_CATALOG
        categories = {p["category"] for p in _BUILTIN_CATALOG}
        assert "devops" in categories
        assert "data" in categories
        assert "web" in categories


# ---------------------------------------------------------------------------
# Model comparison endpoint
# ---------------------------------------------------------------------------

class TestModelComparison:
    """Tests for GET /api/model/compare."""

    def test_compare_imports(self):
        from ggufloader.api.routes.model import model_compare

    def test_compare_requires_two_paths(self):
        from ggufloader.api.routes.model import model_compare

        with pytest.raises(Exception):  # HTTPException
            __import__("asyncio").get_event_loop().run_until_complete(
                model_compare(paths="only_one_path")
            )

    def test_compare_nonexistent_models(self):
        from ggufloader.api.routes.model import model_compare

        result = __import__("asyncio").get_event_loop().run_until_complete(
            model_compare(paths="/fake/a.gguf,/fake/b.gguf")
        )
        assert len(result["models"]) == 2
        assert all("error" in m for m in result["models"])

    def test_compare_with_fake_gguf_files(self):
        """Two small fake GGUF files should be compared (metadata read will fail gracefully)."""
        from ggufloader.api.routes.model import model_compare

        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "model_a.gguf"
            b = Path(tmp) / "model_b.gguf"
            a.write_bytes(b"\x00" * 1024)
            b.write_bytes(b"\x00" * 2048)

            result = __import__("asyncio").get_event_loop().run_until_complete(
                model_compare(paths=f"{a},{b}")
            )
            assert len(result["models"]) == 2
            # Both will have errors since metadata parsing fails on fake files,
            # but the endpoint should still return valid structure
            assert "models" in result
            assert "system" in result

    def test_compare_max_five_models(self):
        """Should cap at 5 models."""
        from ggufloader.api.routes.model import model_compare

        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i in range(7):
                p = Path(tmp) / f"m{i}.gguf"
                p.write_bytes(b"\x00" * 100)
                paths.append(str(p))

            result = __import__("asyncio").get_event_loop().run_until_complete(
                model_compare(paths=",".join(paths))
            )
            assert len(result["models"]) <= 5
