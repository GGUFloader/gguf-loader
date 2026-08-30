"""
MCPBridge - Connect MCP server tools into the agent's ToolRegistry.

Discovers tools from connected MCP servers via JSON-RPC and wraps
each one as a Tool subclass so GraphAgent can call them like any
built-in tool.

Supports:
- stdio-based MCP servers (spawn process, exchange JSON-RPC)
- Tool discovery via `tools/list`
- Tool execution via `tools/call`
- Graceful error handling for crashed/timeout servers
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .tool_registry import Tool, ToolRegistry

logger = logging.getLogger(__name__)


class MCPTool(Tool):
    """A tool discovered from an MCP server, wrapped for the ToolRegistry."""

    def __init__(
        self,
        workspace: Path,
        server_name: str,
        tool_def: Dict[str, Any],
        bridge: "MCPBridge",
    ) -> None:
        super().__init__(workspace)
        self.name = tool_def.get("name", "unknown")
        self.description = tool_def.get("description", "")
        self.schema = tool_def.get("inputSchema", {"type": "object", "properties": {}})
        self._server_name = server_name
        self._bridge = bridge

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        """MCP tools from trusted servers don't require approval by default."""
        return False

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool by calling the MCP server via JSON-RPC."""
        return self._bridge.call_tool(self._server_name, self.name, params)


class MCPServerProcess:
    """Manages a single MCP server subprocess."""

    def __init__(
        self,
        name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self._process: Optional[subprocess.Popen] = None
        self._tools: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._connected = False
        self._request_id = 0

    def connect(self, timeout: float = 10.0) -> bool:
        """Spawn the MCP server and perform handshake."""
        try:
            merged_env = {**os.environ, **self.env}
            self._process = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            # Send initialize request
            self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ggufloader", "version": "1.0"},
            })
            resp = self._read_response(timeout)
            if resp is None:
                logger.warning("MCP server %s: no initialize response", self.name)
                self.disconnect()
                return False

            # Send initialized notification
            self._send_notification("notifications/initialized", {})

            # Discover tools
            self._tools = self._list_tools(timeout)
            self._connected = True
            logger.info(
                "MCP server %s connected, %d tools discovered",
                self.name,
                len(self._tools),
            )
            return True
        except Exception as e:
            logger.error("MCP server %s connect failed: %s", self.name, e)
            self.disconnect()
            return False

    def disconnect(self) -> None:
        """Stop the MCP server process."""
        self._connected = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        self._tools = []

    @property
    def connected(self) -> bool:
        return self._connected and self._process is not None and self._process.poll() is None

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return cached tool definitions."""
        return list(self._tools)

    def call_tool(self, name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """Call a tool on this MCP server via JSON-RPC."""
        if not self.connected:
            return {"status": "error", "error": f"MCP server {self.name} not connected"}
        try:
            self._send_request("tools/call", {"name": name, "arguments": arguments})
            resp = self._read_response(timeout)
            if resp is None:
                return {"status": "error", "error": f"MCP server {self.name} timed out"}

            result = resp.get("result", {})
            # MCP tools/call returns {content: [{type, text}], isError: bool}
            content_parts = result.get("content", [])
            text = "\n".join(p.get("text", "") for p in content_parts if isinstance(p, dict))
            is_error = result.get("isError", False)

            return {
                "status": "error" if is_error else "success",
                "result": text or str(result),
                "tool_name": name,
                "server": self.name,
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": name}

    # --- JSON-RPC transport (stdio) ---

    def _send_request(self, method: str, params: Dict[str, Any]) -> None:
        self._request_id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        self._write(msg)

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self._write(msg)

    def _write(self, msg: dict) -> None:
        if self._process and self._process.stdin:
            data = json.dumps(msg)
            self._process.stdin.write(f"Content-Length: {len(data.encode())}\r\n\r\n{data}")
            self._process.stdin.flush()

    def _read_response(self, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """Read a JSON-RPC response from stdout (Content-Length framing)."""
        if not self._process or not self._process.stdout:
            return None

        def _read():
            # Read Content-Length header
            header = b""
            while True:
                byte = self._process.stdout.read(1)
                if not byte:
                    return None
                header += byte
                if header.endswith(b"\r\n\r\n"):
                    break
            # Parse content length
            for part in header.decode("utf-8", errors="replace").split("\r\n"):
                if part.startswith("Content-Length:"):
                    length = int(part.split(":")[1].strip())
                    body = self._process.stdout.read(length)
                    return json.loads(body.decode("utf-8"))
            return None

        try:
            result = [None]
            def _target():
                result[0] = _read()

            t = threading.Thread(target=_target, daemon=True)
            t.start()
            t.join(timeout)
            if t.is_alive():
                return None  # timeout
            return result[0]
        except Exception:
            return None

    def _list_tools(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """Request tool list from the MCP server."""
        self._send_request("tools/list", {})
        resp = self._read_response(timeout)
        if resp is None:
            return []
        return resp.get("result", {}).get("tools", [])


class MCPBridge:
    """Manages multiple MCP servers and registers their tools with ToolRegistry.

    Usage:
        bridge = MCPBridge(workspace)
        bridge.add_server("filesystem", "npx", ["-y", "@anthropic/mcp-filesystem", "/tmp"])
        bridge.connect_all()
        bridge.register_tools(registry)
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._servers: Dict[str, MCPServerProcess] = {}

    def add_server(
        self,
        name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """Configure an MCP server (doesn't connect yet)."""
        self._servers[name] = MCPServerProcess(name, command, args, env)

    def remove_server(self, name: str) -> None:
        """Disconnect and remove an MCP server."""
        server = self._servers.pop(name, None)
        if server:
            server.disconnect()

    def connect_all(self, timeout: float = 10.0) -> Dict[str, bool]:
        """Connect to all configured MCP servers. Returns {name: success}."""
        results = {}
        for name, server in self._servers.items():
            results[name] = server.connect(timeout)
        return results

    def disconnect_all(self) -> None:
        """Disconnect all MCP servers."""
        for server in self._servers.values():
            server.disconnect()

    def register_tools(self, registry: ToolRegistry) -> int:
        """Discover and register all MCP tools with the ToolRegistry.

        Returns the number of tools registered.
        """
        count = 0
        for name, server in self._servers.items():
            if not server.connected:
                continue
            for tool_def in server.list_tools():
                tool = MCPTool(self.workspace, name, tool_def, self)
                registry.register_instance(tool)
                count += 1
                logger.info("Registered MCP tool: %s (from %s)", tool.name, name)
        return count

    def call_tool(self, server_name: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on a specific MCP server."""
        server = self._servers.get(server_name)
        if not server:
            return {"status": "error", "error": f"MCP server '{server_name}' not found"}
        return server.call_tool(tool_name, params)

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions from all connected servers."""
        tools = []
        for name, server in self._servers.items():
            if server.connected:
                for t in server.list_tools():
                    tools.append({**t, "_server": name})
        return tools

    def get_status(self) -> List[Dict[str, Any]]:
        """Get status of all MCP servers."""
        statuses = []
        for name, server in self._servers.items():
            statuses.append({
                "name": name,
                "connected": server.connected,
                "tools_count": len(server.list_tools()),
                "command": server.command,
            })
        return statuses
