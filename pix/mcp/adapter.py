"""Adapt an MCP tool to PiX's unified Tool interface."""

from __future__ import annotations

from typing import Any

from pix.mcp.client import MCPClient
from pix.tools.base import Tool


class MCPToolAdapter(Tool):
    """A Tool view over a remote MCP tool."""

    def __init__(
        self,
        client: MCPClient,
        name: str,
        description: str,
        parameters: dict[str, Any],
        *,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._client = client
        self.name = name
        self.description = description
        self.parameters = parameters or {"type": "object", "properties": {}}
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: dict[str, Any]) -> Any:
        return self._client.call_tool(self.name, arguments)
