"""MCP clients using the stdio JSON-RPC transport."""

from __future__ import annotations

import json
import logging
import queue
import shlex
import subprocess
import threading
from abc import ABC, abstractmethod
from typing import Any

from pix.errors import ToolError

logger = logging.getLogger(__name__)


class MCPClient(ABC):
    """Abstract remote tool namespace."""

    @abstractmethod
    def start(self) -> None:
        """Initialize the transport and handshake."""

    @abstractmethod
    def list_tools(self) -> list[dict[str, Any]]:
        """Return remote tool definitions."""

    @abstractmethod
    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a remote tool."""

    @abstractmethod
    def close(self) -> None:
        """Release the transport."""


class StdioMCPClient(MCPClient):
    """JSON-RPC over a subprocess's stdin/stdout."""

    def __init__(self, name: str, command: list[str], *, cwd: str | None = None) -> None:
        self.name = name
        self.command = command
        self.cwd = cwd
        self._process: subprocess.Popen[str] | None = None
        self._next_id = 0
        self._lock = threading.Lock()
        self._pending: dict[int, queue.Queue[Any]] = {}
        self._reader: threading.Thread | None = None

    @classmethod
    def from_command_string(cls, name: str, command: str, *, cwd: str | None = None) -> StdioMCPClient:
        tokens = shlex.split(command, posix=True)
        if not tokens:
            raise ValueError(f"MCP server command cannot be empty: {name}")
        return cls(name, tokens, cwd=cwd)

    def start(self) -> None:
        if self._process is not None:
            return
        try:
            self._process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
        except OSError as exc:
            raise ToolError(f"Cannot start MCP server '{self.name}': {exc}") from exc
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pix-agent", "version": "0.1.0"},
            },
        )

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list", {})
        return list(result.get("tools", []))

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            content = result.get("content", [])
            raise ToolError(f"MCP tool '{name}' failed: {content}")
        return result.get("content") or result

    def close(self) -> None:
        if self._process is None:
            return
        try:
            if self._process.stdin:
                self._process.stdin.close()
            self._process.terminate()
            self._process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            self._process.kill()
        finally:
            self._process = None

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        if self._process is None:
            raise ToolError("MCP client is not started")
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            pending: queue.Queue[Any] = queue.Queue(maxsize=1)
            self._pending[request_id] = pending
            payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            try:
                assert self._process.stdin is not None
                self._process.stdin.write(json.dumps(payload) + "\n")
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self._pending.pop(request_id, None)
                raise ToolError(f"MCP request '{method}' failed: {exc}") from exc
        try:
            response = pending.get(timeout=15)
        except queue.Empty as exc:
            self._pending.pop(request_id, None)
            raise ToolError(f"MCP request '{method}' timed out") from exc
        if "error" in response:
            raise ToolError(f"MCP error for '{method}': {response['error']}")
        return response.get("result", {})

    def _read_loop(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        for line in self._process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("jsonrpc") != "2.0":
                continue
            if "id" in message:
                with self._lock:
                    pending = self._pending.pop(int(message["id"]), None)
                if pending is not None:
                    pending.put(message)
