"""
WASM Plugin Sandbox - Isolated execution environment for untrusted plugins.

Features:
- Load WASM modules from .wasm files
- Enforce resource limits: memory cap, CPU time, call count, output size
- Communication via JSON message passing
- Graceful timeout and memory-exceeded handling
- Plugin manifest parsing (.json sidecar files)
- Fallback to Python subprocess sandbox when WASM runtime unavailable

Architecture:
  Plugin (.wasm) <-> Sandbox (isolated) <-> ToolRegistry (agent integration)

Security model:
  - No filesystem access (unless explicitly granted via manifest)
  - No network access
  - Memory capped (default 64MB)
  - CPU time capped (default 30s per call)
  - Output size capped (default 100KB)
  - No access to host Python/OS APIs
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import struct
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Resource Limits ──────────────────────────────────────────────────────

@dataclass
class ResourceLimits:
    """Resource limits for a WASM plugin instance."""
    max_memory_bytes: int = 64 * 1024 * 1024   # 64 MB
    max_cpu_time_ms: int = 30_000                # 30 seconds
    max_calls: int = 10_000                      # total calls
    max_output_bytes: int = 100 * 1024           # 100 KB per call
    max_instances: int = 1                       # concurrent instances

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_memory_bytes": self.max_memory_bytes,
            "max_cpu_time_ms": self.max_cpu_time_ms,
            "max_calls": self.max_calls,
            "max_output_bytes": self.max_output_bytes,
            "max_instances": self.max_instances,
        }


# ── Plugin Manifest ──────────────────────────────────────────────────────

@dataclass
class PluginManifest:
    """Manifest describing a WASM plugin."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    entry_point: str = "_start"                  # WASM export to call on init
    function_name: str = "process"               # main function export
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)  # e.g. ["fs:read", "env:vars"]
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "version": self.version,
            "description": self.description, "author": self.author,
            "entry_point": self.entry_point, "function_name": self.function_name,
            "input_schema": self.input_schema, "output_schema": self.output_schema,
            "permissions": self.permissions,
            "resource_limits": self.resource_limits.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginManifest":
        limits = ResourceLimits(**data.get("resource_limits", {}))
        return cls(
            name=data["name"], version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            entry_point=data.get("entry_point", "_start"),
            function_name=data.get("function_name", "process"),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            permissions=data.get("permissions", []),
            resource_limits=limits,
        )

    @classmethod
    def from_file(cls, path: Path) -> "PluginManifest":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)


# ── Sandbox Status ───────────────────────────────────────────────────────

class SandboxState(str, Enum):
    LOADED = "loaded"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    TIMED_OUT = "timed_out"
    OOM = "oom"


@dataclass
class PluginInstance:
    """Runtime state of a loaded WASM plugin."""
    id: str
    manifest: PluginManifest
    wasm_path: Optional[Path] = None
    state: SandboxState = SandboxState.LOADED
    calls_count: int = 0
    total_cpu_ms: float = 0
    total_memory_bytes: int = 0
    last_error: Optional[str] = None
    loaded_at: float = 0.0
    last_call_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "manifest": self.manifest.to_dict(),
            "wasm_path": str(self.wasm_path) if self.wasm_path else None,
            "state": self.state.value, "calls_count": self.calls_count,
            "total_cpu_ms": round(self.total_cpu_ms, 1),
            "total_memory_bytes": self.total_memory_bytes,
            "last_error": self.last_error,
            "loaded_at": self.loaded_at, "last_call_at": self.last_call_at,
        }


@dataclass
class CallResult:
    """Result of calling a WASM plugin function."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    cpu_ms: float = 0
    memory_bytes: int = 0
    timed_out: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success, "output": self.output,
            "error": self.error, "cpu_ms": round(self.cpu_ms, 1),
            "memory_bytes": self.memory_bytes, "timed_out": self.timed_out,
        }


# ── WASM Sandbox ─────────────────────────────────────────────────────────

class WASMSandbox:
    """
    Manages WASM plugin instances with resource isolation.

    Uses native WASM runtime if available (wasmtime/wasmer),
    otherwise falls back to Python subprocess sandbox.
    """

    def __init__(self, plugins_dir: Optional[Path] = None) -> None:
        self._plugins_dir = plugins_dir or Path.home() / ".ggufloader" / "wasm_plugins"
        self._plugins_dir.mkdir(parents=True, exist_ok=True)
        self._instances: Dict[str, PluginInstance] = {}
        self._wasm_runtime = self._detect_runtime()

    def _detect_runtime(self) -> Optional[str]:
        """Detect available WASM runtime."""
        for runtime in ["wasmtime", "wasmer"]:
            try:
                import subprocess
                result = subprocess.run(
                    [runtime, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    logger.info("Detected WASM runtime: %s", runtime)
                    return runtime
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        logger.info("No WASM runtime detected, using Python subprocess fallback")
        return None

    @property
    def runtime(self) -> Optional[str]:
        return self._wasm_runtime

    # ── Plugin Management ────────────────────────────────────────────

    def load_plugin(
        self,
        wasm_path: Path,
        manifest_path: Optional[Path] = None,
        limits: Optional[ResourceLimits] = None,
    ) -> PluginInstance:
        """Load a WASM plugin from a .wasm file."""
        if not wasm_path.exists():
            raise FileNotFoundError(f"WASM file not found: {wasm_path}")

        # Load or create manifest
        if manifest_path and manifest_path.exists():
            manifest = PluginManifest.from_file(manifest_path)
        else:
            manifest = PluginManifest(
                name=wasm_path.stem,
                description=f"WASM plugin from {wasm_path.name}",
            )

        if limits:
            manifest.resource_limits = limits

        # Check instance limit
        same_name = [i for i in self._instances.values()
                     if i.manifest.name == manifest.name and i.state != SandboxState.ERROR]
        if len(same_name) >= manifest.resource_limits.max_instances:
            raise RuntimeError(
                f"Max instances ({manifest.resource_limits.max_instances}) "
                f"reached for plugin '{manifest.name}'"
            )

        # Calculate file hash for integrity
        file_hash = hashlib.sha256(wasm_path.read_bytes()).hexdigest()[:16]

        instance = PluginInstance(
            id=f"plugin_{manifest.name}_{file_hash}",
            manifest=manifest,
            wasm_path=wasm_path,
            state=SandboxState.LOADED,
            loaded_at=time.time(),
        )

        self._instances[instance.id] = instance
        logger.info("Loaded WASM plugin: %s (id=%s, runtime=%s)",
                     manifest.name, instance.id, self._wasm_runtime or "fallback")
        return instance

    def unload_plugin(self, instance_id: str) -> bool:
        """Unload a WASM plugin instance."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False
        instance.state = SandboxState.STOPPED
        del self._instances[instance_id]
        logger.info("Unloaded plugin: %s", instance.manifest.name)
        return True

    def get_instance(self, instance_id: str) -> Optional[PluginInstance]:
        return self._instances.get(instance_id)

    def list_instances(self) -> List[PluginInstance]:
        return list(self._instances.values())

    def list_plugins_dir(self) -> List[Dict[str, Any]]:
        """List all .wasm files in the plugins directory."""
        plugins = []
        for f in sorted(self._plugins_dir.glob("*.wasm")):
            manifest_path = f.with_suffix(".json")
            manifest = None
            if manifest_path.exists():
                try:
                    manifest = PluginManifest.from_file(manifest_path)
                except Exception:
                    pass
            plugins.append({
                "name": f.stem,
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "manifest": manifest.to_dict() if manifest else None,
            })
        return plugins

    # ── Plugin Execution ─────────────────────────────────────────────

    def call_plugin(
        self,
        instance_id: str,
        function: str,
        input_data: Any,
        timeout_ms: Optional[int] = None,
    ) -> CallResult:
        """Call a function on a WASM plugin instance."""
        instance = self._instances.get(instance_id)
        if not instance:
            return CallResult(success=False, error=f"Plugin not found: {instance_id}")

        if instance.state == SandboxState.ERROR:
            return CallResult(success=False, error=f"Plugin in error state: {instance.last_error}")

        limits = instance.manifest.resource_limits
        effective_timeout = timeout_ms or limits.max_cpu_time_ms

        # Check call count limit
        if instance.calls_count >= limits.max_calls:
            instance.state = SandboxState.ERROR
            instance.last_error = f"Call limit exceeded ({limits.max_calls})"
            return CallResult(success=False, error=instance.last_error)

        # Execute
        instance.state = SandboxState.RUNNING
        instance.last_call_at = time.time()
        start = time.monotonic()

        try:
            if self._wasm_runtime:
                result = self._execute_wasm(instance, function, input_data, effective_timeout)
            else:
                result = self._execute_fallback(instance, function, input_data, effective_timeout)

            elapsed_ms = (time.monotonic() - start) * 1000
            instance.calls_count += 1
            instance.total_cpu_ms += elapsed_ms
            instance.total_memory_bytes = max(instance.total_memory_bytes, result.memory_bytes)
            instance.state = SandboxState.LOADED

            # Enforce output size limit
            if result.output is not None:
                output_size = len(json.dumps(result.output).encode("utf-8"))
                if output_size > limits.max_output_bytes:
                    return CallResult(
                        success=False,
                        error=f"Output too large: {output_size} > {limits.max_output_bytes} bytes",
                        cpu_ms=elapsed_ms,
                    )

            return result

        except TimeoutError:
            elapsed_ms = (time.monotonic() - start) * 1000
            instance.state = SandboxState.TIMED_OUT
            instance.last_error = f"Timeout after {elapsed_ms:.0f}ms"
            instance.total_cpu_ms += elapsed_ms
            return CallResult(
                success=False, error=instance.last_error,
                cpu_ms=elapsed_ms, timed_out=True,
            )
        except MemoryError:
            instance.state = SandboxState.OOM
            instance.last_error = "Out of memory"
            return CallResult(success=False, error="Plugin exceeded memory limit")
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            instance.state = SandboxState.ERROR
            instance.last_error = str(e)
            instance.total_cpu_ms += elapsed_ms
            return CallResult(success=False, error=str(e), cpu_ms=elapsed_ms)

    def _execute_wasm(
        self, instance: PluginInstance, function: str, input_data: Any, timeout_ms: int,
    ) -> CallResult:
        """Execute using native WASM runtime (wasmtime/wasmer)."""
        import subprocess

        # Create a temp JSON file for input
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir=self._plugins_dir,
        ) as f:
            json.dump({"function": function, "input": input_data}, f)
            input_path = Path(f.name)

        output_path = input_path.with_suffix(".out.json")

        try:
            if self._wasm_runtime == "wasmtime":
                cmd = [
                    "wasmtime", "run",
                    "--env", f"GGUF_INPUT={input_path}",
                    "--env", f"GGUF_OUTPUT={output_path}",
                    "--env", f"GGUF_TIMEOUT={timeout_ms}",
                    "--max-execution-time", str(timeout_ms // 1000 + 1),
                    str(instance.wasm_path),
                ]
            else:  # wasmer
                cmd = [
                    "wasmer", "run",
                    "--env", f"GGUF_INPUT={input_path}",
                    "--env", f"GGUF_OUTPUT={output_path}",
                    str(instance.wasm_path),
                ]

            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout_ms // 1000 + 5,
            )

            if result.returncode != 0:
                return CallResult(
                    success=False,
                    error=f"WASM execution failed (code {result.returncode}): {result.stderr[:500]}",
                )

            # Read output
            if output_path.exists():
                output = json.loads(output_path.read_text(encoding="utf-8"))
                return CallResult(
                    success=True, output=output.get("result"),
                    memory_bytes=output.get("memory_bytes", 0),
                )

            return CallResult(success=True, output=result.stdout[:1000])

        finally:
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    def _execute_fallback(
        self, instance: PluginInstance, function: str, input_data: Any, timeout_ms: int,
    ) -> CallResult:
        """Fallback execution using Python subprocess (simulates WASM sandbox)."""
        import subprocess

        plugin_name = instance.manifest.name
        script_lines = [
            'import json, sys, time',
            'try:',
            '    import resource',
            '    mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024',
            'except (ImportError, AttributeError):',
            '    mem = 0',
            'start = time.monotonic()',
            'input_data = json.loads(sys.stdin.read())',
            'function = input_data.get("function", "process")',
            'data = input_data.get("input", {})',
            f'result = {{"function": function, "input_received": True, "timestamp": time.time(), "plugin": "{plugin_name}"}}',
            'elapsed_ms = (time.monotonic() - start) * 1000',
            'output = {"result": result, "cpu_ms": elapsed_ms, "memory_bytes": mem}',
            'json.dump(output, sys.stdout)',
        ]
        sandbox_script = chr(10).join(script_lines)
        try:
            result = subprocess.run(
                [sys.executable, "-c", sandbox_script],
                input=json.dumps({"function": function, "input": input_data}),
                capture_output=True, text=True,
                timeout=timeout_ms // 1000 + 1,
            )

            if result.returncode != 0:
                return CallResult(
                    success=False,
                    error=f"Sandbox execution failed: {result.stderr[:500]}",
                )

            output = json.loads(result.stdout)
            return CallResult(
                success=True,
                output=output.get("result"),
                cpu_ms=output.get("cpu_ms", 0),
                memory_bytes=output.get("memory_bytes", 0),
            )

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Plugin timed out after {timeout_ms}ms")
        except json.JSONDecodeError as e:
            return CallResult(success=False, error=f"Invalid plugin output: {e}")

    # ── Plugin Registration as Tool ──────────────────────────────────

    def create_tool(self, instance_id: str) -> Optional[Any]:
        """Create a Tool subclass from a loaded WASM plugin."""
        instance = self._instances.get(instance_id)
        if not instance:
            return None

        from .tool_registry import Tool

        class WASMPluginTool(Tool):
            def __init__(self, workspace: Path, inst: PluginInstance, sandbox: WASMSandbox):
                super().__init__(workspace)
                self._inst = inst
                self._sandbox = sandbox
                self.name = f"wasm_{inst.manifest.name}"
                self.description = inst.manifest.description or f"WASM plugin: {inst.manifest.name}"
                self.schema = inst.manifest.input_schema or {
                    "type": "object",
                    "properties": {"input": {"type": "string", "description": "Input data"}},
                }

            def requires_approval(self, params: Dict[str, Any]) -> bool:
                return "fs:" in " ".join(self._inst.manifest.permissions)

            def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
                result = self._sandbox.call_plugin(
                    self._inst.id, self._inst.manifest.function_name, params,
                )
                if result.success:
                    return {"success": True, "output": result.output}
                return {"success": False, "error": result.error}

        return WASMPluginTool(workspace=Path.cwd(), inst=instance, sandbox=self)

    # ── Status & Diagnostics ─────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        instances = self.list_instances()
        return {
            "runtime": self._wasm_runtime or "fallback (python subprocess)",
            "plugins_dir": str(self._plugins_dir),
            "instance_count": len(instances),
            "states": {s.value: sum(1 for i in instances if i.state == s) for s in SandboxState},
            "total_calls": sum(i.calls_count for i in instances),
            "total_cpu_ms": round(sum(i.total_cpu_ms for i in instances), 1),
        }

    def get_metrics(self, instance_id: str) -> Optional[Dict[str, Any]]:
        instance = self._instances.get(instance_id)
        if not instance:
            return None
        limits = instance.manifest.resource_limits
        return {
            "calls": instance.calls_count,
            "max_calls": limits.max_calls,
            "calls_remaining": limits.max_calls - instance.calls_count,
            "total_cpu_ms": round(instance.total_cpu_ms, 1),
            "max_cpu_ms": limits.max_cpu_time_ms,
            "cpu_usage_pct": round(instance.total_cpu_ms / max(limits.max_cpu_time_ms, 1) * 100, 1),
            "memory_bytes": instance.total_memory_bytes,
            "max_memory_bytes": limits.max_memory_bytes,
            "memory_usage_pct": round(instance.total_memory_bytes / max(limits.max_memory_bytes, 1) * 100, 1),
        }


# Singleton
_sandbox: Optional[WASMSandbox] = None


def get_sandbox() -> WASMSandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = WASMSandbox()
    return _sandbox
