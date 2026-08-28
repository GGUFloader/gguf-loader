"""
MCPClient - Model Context Protocol client for external tool servers.

Pattern from: OpenHands MCP integration + Claude Code MCP.
Enables GGUFLoader to connect to external MCP servers and use their
tools alongside built-in tools. Supports:

1. stdio-based MCP servers (subprocess communication)
2. Tool discovery and registration
3. Tool execution via JSON-RPC
4. Automatic reconnection on failure

MCP is the emerging standard for AI tool servers (used by Claude,
Cursor, OpenHands). This client lets GGUFLoader plug into that
ecosystem.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .tool_registry import Tool, ToolRegistry

logger = logging.getLogger(__name__)

# MCP JSON-RPC version
MCP_JSONRPC_VERSION = "2.0"

# Default timeout for MCP operations
DEFAULT_TIMEOUT = 30


class MCPTool(Tool):
    """A tool provided by an external MCP server."""

    def __init__(self, workspace: Path, name: str, description: str,
                 input_schema: Dict[str, Any], server: "MCPServer") -> None:
        super().__init__(workspace)
        self.name = name
        self.description = description
        self.schema = input_schema
        self._server = server

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        # MCP tools default to requiring approval (safe by default)
        return True

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self._server.call_tool(self.name, params)
            return {
                "status": "success",
                "result": result,
                "tool_name": self.name,
                "source": "mcp",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "tool_name": self.name,
                "source": "mcp",
            }


class MCPServer:
    """Connection to a single MCP server (stdio transport).

    Usage:
        server = MCPServer("my-server", ["python", "-m", "my_mcp_server"])
        server.start()
        tools = server.list_tools()
        result = server.call_tool("my_tool", {"arg": "value"})
        server.stop()
    """

    def __init__(self, name: str, command: List[str], env: Dict[str, str] = None,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.name = name
        self.command = command
        self.env = env
        self._timeout = timeout
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._tools_cache: List[Dict[str, Any]] = []
        self._connected = False

    def start(self) -> bool:
        """Start the MCP server subprocess."""
        try:
            import os
            server_env = dict(os.environ)
            if self.env:
                server_env.update(self.env)

            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=server_env,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # Initialize the connection
            self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ggufloader", "version": "1.0.0"},
            })

            # Send initialized notification
            self._send_notification("notifications/initialized", {})

            self._connected = True
            logger.info("MCP server '%s' started (pid=%d)", self.name, self._process.pid)
            return True

        except Exception as e:
            logger.error("Failed to start MCP server '%s': %s", self.name, e)
            self._connected = False
            return False

    def stop(self) -> None:
        """Stop the MCP server subprocess."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._process is not None and self._process.poll() is None

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server."""
        if not self.is_connected:
            return self._tools_cache

        try:
            result = self._send_request("tools/list", {})
            tools = result.get("tools", [])
            self._tools_cache = tools
            return tools
        except Exception as e:
            logger.error("Failed to list tools from '%s': %s", self.name, e)
            return self._tools_cache

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the server."""
        if not self.is_connected:
            raise ConnectionError(f"MCP server '{self.name}' is not connected")

        result = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        # MCP returns content array
        content = result.get("content", [])
        if content:
            # Extract text from first text content
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    return item.get("text", "")
            return content
        return result

    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and wait for response."""
        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        request = {
            "jsonrpc": MCP_JSONRPC_VERSION,
            "id": request_id,
            "method": method,
            "params": params,
        }

        # Send
        message = json.dumps(request)
        header = f"Content-Length: {len(message.encode())}\r\n\r\n"

        self._process.stdin.write(header + message)
        self._process.stdin.flush()

        # Read response
        response = self._read_response()
        if response is None:
            raise TimeoutError(f"No response from MCP server '{self.name}'")

        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"MCP error: {error.get('message', error)}")

        return response.get("result", {})

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        notification = {
            "jsonrpc": MCP_JSONRPC_VERSION,
            "method": method,
            "params": params,
        }
        message = json.dumps(notification)
        header = f"Content-Length: {len(message.encode())}\r\n\r\n"
        self._process.stdin.write(header + message)
        self._process.stdin.flush()

    def _read_response(self) -> Optional[Dict[str, Any]]:
        """Read a JSON-RPC response from stdout."""
        # Read Content-Length header
        content_length = 0
        deadline = time.time() + self._timeout

        while time.time() < deadline:
            line = self._process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if line.startswith("Content-Length:"):
                content_length = int(line.split(":")[1].strip())
                break

        if content_length <= 0:
            return None

        # Read body
        body = self._process.stdout.read(content_length)
        return json.loads(body)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "connected": self.is_connected,
            "tools_cached": len(self._tools_cache),
            "pid": self._process.pid if self._process else None,
        }


class MCPClient:
    """Manage multiple MCP server connections and register their tools.

    Usage:
        client = MCPClient(workspace)

        # Add servers
        client.add_server("filesystem", ["npx", "-y", "@anthropic/mcp-filesystem"])

        # Connect and discover tools
        client.connect_all()
        client.register_tools(registry)

        # Use tools (they appear as regular tools in the registry)
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._servers: Dict[str, MCPServer] = {}
        self._loaded_tools: Dict[str, MCPTool] = {}

    def add_server(self, name: str, command: List[str], env: Dict[str, str] = None,
                   timeout: float = DEFAULT_TIMEOUT) -> None:
        """Add an MCP server configuration."""
        self._servers[name] = MCPServer(name, command, env, timeout)

    def remove_server(self, name: str) -> None:
        """Remove and stop an MCP server."""
        server = self._servers.pop(name, None)
        if server:
            server.stop()
        # Remove tools from this server
        self._loaded_tools = {
            k: v for k, v in self._loaded_tools.items()
            if v._server.name != name
        }

    def connect_all(self) -> Dict[str, bool]:
        """Connect to all configured servers. Returns {name: success}."""
        results = {}
        for name, server in self._servers.items():
            results[name] = server.start()
            if results[name]:
                # Discover tools
                tools = server.list_tools()
                for tool_info in tools:
                    tool_name = tool_info.get("name", "")
                    if tool_name:
                        mcp_tool = MCPTool(
                            workspace=self.workspace,
                            name=f"mcp_{name}_{tool_name}",
                            description=tool_info.get("description", ""),
                            input_schema=tool_info.get("inputSchema", {}),
                            server=server,
                        )
                        self._loaded_tools[mcp_tool.name] = mcp_tool
        return results

    def disconnect_all(self) -> None:
        """Stop all MCP servers."""
        for server in self._servers.values():
            server.stop()
        self._loaded_tools.clear()

    def register_tools(self, registry: ToolRegistry) -> int:
        """Register all discovered MCP tools with a ToolRegistry."""
        count = 0
        for tool in self._loaded_tools.values():
            registry.register_instance(tool)
            count += 1
        return count

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get info about all discovered MCP tools."""
        return [
            {"name": t.name, "description": t.description, "server": t._server.name}
            for t in self._loaded_tools.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "servers": len(self._servers),
            "connected": sum(1 for s in self._servers.values() if s.is_connected),
            "tools": len(self._loaded_tools),
            "server_stats": {n: s.get_stats() for n, s in self._servers.items()},
        }
