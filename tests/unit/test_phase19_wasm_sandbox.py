"""Tests for Phase 19: WASM Plugin Sandbox."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest


# ── WASM Sandbox Core ────────────────────────────────────────────────────


class TestWASMSandbox:
    """Tests for the WASM sandbox core."""

    def test_imports(self):
        from ggufloader.core.agent.wasm_sandbox import (
            WASMSandbox, PluginInstance, PluginManifest,
            ResourceLimits, SandboxState, CallResult,
        )

    def test_resource_limits_defaults(self):
        from ggufloader.core.agent.wasm_sandbox import ResourceLimits

        limits = ResourceLimits()
        assert limits.max_memory_bytes == 64 * 1024 * 1024
        assert limits.max_cpu_time_ms == 30_000
        assert limits.max_calls == 10_000
        assert limits.max_output_bytes == 100 * 1024

    def test_resource_limits_custom(self):
        from ggufloader.core.agent.wasm_sandbox import ResourceLimits

        limits = ResourceLimits(max_memory_bytes=1024, max_cpu_time_ms=5000)
        d = limits.to_dict()
        assert d["max_memory_bytes"] == 1024
        assert d["max_cpu_time_ms"] == 5000

    def test_plugin_manifest(self):
        from ggufloader.core.agent.wasm_sandbox import PluginManifest

        manifest = PluginManifest(
            name="test_plugin", version="1.0.0", description="Test",
            author="tester", permissions=["fs:read"],
        )
        d = manifest.to_dict()
        assert d["name"] == "test_plugin"
        assert d["permissions"] == ["fs:read"]

    def test_plugin_manifest_from_dict(self):
        from ggufloader.core.agent.wasm_sandbox import PluginManifest

        data = {
            "name": "my_plugin", "version": "2.0.0",
            "description": "A plugin",
            "permissions": ["env:vars"],
            "resource_limits": {"max_memory_bytes": 1024 * 1024},
        }
        manifest = PluginManifest.from_dict(data)
        assert manifest.name == "my_plugin"
        assert manifest.version == "2.0.0"
        assert manifest.resource_limits.max_memory_bytes == 1024 * 1024

    def test_plugin_manifest_from_file(self):
        from ggufloader.core.agent.wasm_sandbox import PluginManifest

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"name": "file_plugin", "version": "1.0.0"}, f)
            path = Path(f.name)

        manifest = PluginManifest.from_file(path)
        assert manifest.name == "file_plugin"
        path.unlink()

    def test_sandbox_init(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            assert sandbox._plugins_dir.exists()

    def test_sandbox_list_empty(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            plugins = sandbox.list_plugins_dir()
            assert len(plugins) == 0

    def test_sandbox_load_plugin(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            wasm = Path(td) / "test.wasm"
            wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")  # WASM magic bytes

            instance = sandbox.load_plugin(wasm)
            assert instance.manifest.name == "test"
            assert instance.state.value == "loaded"

    def test_sandbox_load_with_manifest(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            wasm = Path(td) / "test.wasm"
            wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")
            manifest = Path(td) / "test.json"
            manifest.write_text(json.dumps({
                "name": "custom_name", "version": "2.0.0",
                "description": "Custom plugin",
                "permissions": ["fs:read", "net:http"],
            }))

            instance = sandbox.load_plugin(wasm, manifest)
            assert instance.manifest.name == "custom_name"
            assert "fs:read" in instance.manifest.permissions

    def test_sandbox_load_with_custom_limits(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox, ResourceLimits

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            wasm = Path(td) / "test.wasm"
            wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")
            limits = ResourceLimits(max_memory_bytes=1024, max_calls=100)

            instance = sandbox.load_plugin(wasm, limits=limits)
            assert instance.manifest.resource_limits.max_memory_bytes == 1024
            assert instance.manifest.resource_limits.max_calls == 100

    def test_sandbox_unload(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            wasm = Path(td) / "test.wasm"
            wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")

            instance = sandbox.load_plugin(wasm)
            unloaded = sandbox.unload_plugin(instance.id)
            assert unloaded is True
            assert len(sandbox.list_instances()) == 0

    def test_sandbox_unload_nonexistent(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            assert sandbox.unload_plugin("nonexistent") is False

    def test_sandbox_list_instances(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            for i in range(3):
                wasm = Path(td) / f"test{i}.wasm"
                wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")
                sandbox.load_plugin(wasm)

            instances = sandbox.list_instances()
            assert len(instances) == 3

    def test_sandbox_list_plugins_dir(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            plugins_dir = Path(td) / "plugins"
            plugins_dir.mkdir()
            (plugins_dir / "a.wasm").write_bytes(b"\x00asm")
            (plugins_dir / "b.wasm").write_bytes(b"\x00asm")

            sandbox = WASMSandbox(plugins_dir)
            plugins = sandbox.list_plugins_dir()
            assert len(plugins) == 2

    def test_sandbox_status(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            status = sandbox.status()
            assert "runtime" in status
            assert "instance_count" in status
            assert status["instance_count"] == 0

    def test_sandbox_call_plugin(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            wasm = Path(td) / "test.wasm"
            wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")
            instance = sandbox.load_plugin(wasm)

            result = sandbox.call_plugin(instance.id, "process", {"input": "hello"})
            assert result.success is True
            assert result.output is not None

    def test_sandbox_call_nonexistent(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            result = sandbox.call_plugin("nonexistent", "process", {})
            assert result.success is False
            assert "not found" in result.error.lower()

    def test_sandbox_call_count_limit(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox, ResourceLimits

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            wasm = Path(td) / "test.wasm"
            wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")
            limits = ResourceLimits(max_calls=3)
            instance = sandbox.load_plugin(wasm, limits=limits)

            for _ in range(3):
                result = sandbox.call_plugin(instance.id, "process", {})
                assert result.success is True

            # 4th call should fail
            result = sandbox.call_plugin(instance.id, "process", {})
            assert result.success is False
            assert "limit" in result.error.lower()

    def test_sandbox_get_metrics(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            wasm = Path(td) / "test.wasm"
            wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")
            instance = sandbox.load_plugin(wasm)

            sandbox.call_plugin(instance.id, "process", {"test": 1})
            metrics = sandbox.get_metrics(instance.id)
            assert metrics is not None
            assert metrics["calls"] == 1

    def test_sandbox_get_metrics_nonexistent(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            assert sandbox.get_metrics("nonexistent") is None

    def test_sandbox_create_tool(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            wasm = Path(td) / "test.wasm"
            wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")
            instance = sandbox.load_plugin(wasm)

            tool = sandbox.create_tool(instance.id)
            assert tool is not None
            assert tool.name == "wasm_test"

    def test_sandbox_create_tool_nonexistent(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            assert sandbox.create_tool("nonexistent") is None

    def test_sandbox_max_instances(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox, ResourceLimits

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            wasm = Path(td) / "test.wasm"
            wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")
            limits = ResourceLimits(max_instances=1)
            sandbox.load_plugin(wasm, limits=limits)

            with pytest.raises(RuntimeError, match="Max instances"):
                sandbox.load_plugin(wasm, limits=limits)

    def test_sandbox_file_not_found(self):
        from ggufloader.core.agent.wasm_sandbox import WASMSandbox

        with tempfile.TemporaryDirectory() as td:
            sandbox = WASMSandbox(Path(td) / "plugins")
            with pytest.raises(FileNotFoundError):
                sandbox.load_plugin(Path(td) / "nonexistent.wasm")


# ── Singleton ────────────────────────────────────────────────────────────


class TestSandboxSingleton:
    def test_singleton(self):
        from ggufloader.core.agent.wasm_sandbox import get_sandbox

        s1 = get_sandbox()
        s2 = get_sandbox()
        assert s1 is s2


# ── API Routes ───────────────────────────────────────────────────────────


class TestSandboxRoutes:
    def test_imports(self):
        from ggufloader.api.routes.sandbox import router
        assert router is not None

    def test_sandbox_router_registered(self):
        from ggufloader.api.app import create_app
        app = create_app()
        routes = [str(getattr(r, 'path', r)) for r in app.routes]
        assert any("sandbox" in r for r in routes)

    def test_sandbox_endpoints_count(self):
        from ggufloader.api.routes.sandbox import router
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        assert len(paths) >= 7  # status, plugins, instances, load, upload, call, metrics, delete
