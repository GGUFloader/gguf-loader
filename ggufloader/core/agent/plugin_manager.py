"""
PluginManager - Runtime plugin loading for agent tools.

Supports two plugin types:
1. JSON tool definitions (schema + command templates)
2. Python modules with a Tool subclass

Plugins are loaded from a configurable directory and registered
with the ToolRegistry at agent startup.

Pattern from: Pydantic AI Harness capability creation + Aider's
extensible tool system.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .tool_registry import Tool, ToolRegistry

logger = logging.getLogger(__name__)

# Default plugin directories
DEFAULT_PLUGIN_DIRS = [
    Path.home() / ".ggufloader" / "plugins",
    Path.home() / ".ggufloader" / "tools",
]


class JsonTool(Tool):
    """A tool defined by a JSON configuration file.

    The JSON defines:
    - name, description, schema (like built-in tools)
    - command_template: shell command with {param} placeholders
    - approval_required: bool
    - timeout: int (seconds)
    """

    def __init__(self, workspace: Path, config: Dict[str, Any]) -> None:
        super().__init__(workspace)
        self.name = config["name"]
        self.description = config.get("description", "")
        self.schema = config.get("schema", {"type": "object", "properties": {}})
        self._command_template = config.get("command_template", "")
        self._approval_required = config.get("approval_required", False)
        self._timeout = config.get("timeout", 60)
        self._cwd_template = config.get("cwd", ".")

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        return self._approval_required

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            command = self._command_template
            for key, value in params.items():
                command = command.replace(f"{{{key}}}", str(value))

            cwd = self.workspace / self._cwd_template
            for key, value in params.items():
                cwd = Path(str(cwd).replace(f"{{{key}}}", str(value)))

            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout,
            )
            output = ((proc.stdout or "") + (proc.stderr or "")).strip()
            return {
                "status": "success" if proc.returncode == 0 else "error",
                "result": output[:8000],
                "returncode": proc.returncode,
                "tool_name": self.name,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"Timed out after {self._timeout}s",
                    "tool_name": self.name}
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": self.name}


class PythonTool(Tool):
    """A tool loaded from a Python module.

    The module must define a class that inherits from Tool and has
    a `name` class attribute. The class is instantiated with the
    workspace path.
    """

    def __init__(self, workspace: Path, module_path: Path,
                 class_name: str = "Tool") -> None:
        # Load the module first to get name/description
        spec = importlib.util.spec_from_file_location(
            f"plugin_{module_path.stem}", str(module_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load plugin: {module_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod.__name__] = mod
        spec.loader.exec_module(mod)

        tool_cls = getattr(mod, class_name, None)
        if tool_cls is None:
            raise AttributeError(f"No class '{class_name}' in {module_path}")

        # Instantiate with workspace
        self._instance = tool_cls(workspace)
        self.name = self._instance.name
        self.description = self._instance.description
        self.schema = getattr(self._instance, "schema", {})

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        return self._instance.requires_approval(params)

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._instance.execute(params)


class PluginManager:
    """Discover, load, and register agent tools from the filesystem.

    Scan order:
    1. ~/.ggufloader/plugins/*.json  (JSON tool definitions)
    2. ~/.ggufloader/tools/*.py      (Python tool modules)
    3. workspace/.ggufloader-tools/  (project-local tools)
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._loaded: Dict[str, str] = {}  # name -> source path

    def discover(self) -> List[Path]:
        """Find all plugin files in configured directories."""
        plugins = []
        dirs = list(DEFAULT_PLUGIN_DIRS)
        # Add workspace-local plugin directory
        workspace_plugins = self.workspace / ".ggufloader-tools"
        if workspace_plugins.is_dir():
            dirs.append(workspace_plugins)

        for d in dirs:
            if not d.is_dir():
                continue
            for f in sorted(d.iterdir()):
                if f.suffix == ".json" and f.is_file():
                    plugins.append(f)
                elif f.suffix == ".py" and f.is_file() and not f.name.startswith("_"):
                    plugins.append(f)
        return plugins

    def load_all(self, registry: ToolRegistry) -> Dict[str, str]:
        """Load all discovered plugins into the registry.

        Returns a dict of {name: status} for each plugin.
        """
        results = {}
        for plugin_path in self.discover():
            name, status = self._load_one(plugin_path, registry)
            results[name] = status
        return results

    def _load_one(self, path: Path, registry: ToolRegistry) -> tuple[str, str]:
        """Load a single plugin. Returns (name, status_message)."""
        try:
            if path.suffix == ".json":
                return self._load_json(path, registry)
            elif path.suffix == ".py":
                return self._load_python(path, registry)
        except Exception as e:
            name = path.stem
            logger.warning("Failed to load plugin %s: %s", path.name, e)
            return name, f"error: {e}"
        return path.stem, "unknown type"

    def _load_json(self, path: Path, registry: ToolRegistry) -> tuple[str, str]:
        """Load a JSON tool definition."""
        config = json.loads(path.read_text(encoding="utf-8"))
        if "name" not in config:
            return path.stem, "error: missing 'name' field"

        name = config["name"]
        tool = JsonTool(self.workspace, config)
        registry.register_instance(tool)
        self._loaded[name] = str(path)
        logger.info("Loaded JSON plugin: %s from %s", name, path.name)
        return name, "loaded"

    def _load_python(self, path: Path, registry: ToolRegistry) -> tuple[str, str]:
        """Load a Python tool module."""
        tool = PythonTool(self.workspace, path)
        registry.register_instance(tool)
        self._loaded[tool.name] = str(path)
        logger.info("Loaded Python plugin: %s from %s", tool.name, path.name)
        return tool.name, "loaded"

    def get_loaded(self) -> Dict[str, str]:
        """Return {name: source_path} of all loaded plugins."""
        return dict(self._loaded)

    def reload(self, registry: ToolRegistry) -> Dict[str, str]:
        """Reload all plugins (drop existing plugin tools first)."""
        # Remove previously loaded plugin tools
        for name in list(self._loaded.keys()):
            registry.unregister(name)
        self._loaded.clear()
        return self.load_all(registry)
