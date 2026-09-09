"""Registry of connected MCP servers and their adapted tools."""

from __future__ import annotations

from typing import Any

from pix.mcp.adapter import MCPToolAdapter
from pix.mcp.client import MCPClient
from pix.tools.registry import ToolRegistry


class MCPRegistry:
    """Own MCP client lifecycles and expose adapted tools to the local registry."""

    def __init__(self) -> None:
        self._clients: dict[str, MCPClient] = {}
        self._tools: dict[str, MCPToolAdapter] = {}

    def register_server(self, name: str, client: MCPClient) -> list[MCPToolAdapter]:
        client.start()
        self._clients[name] = client
        adapters: list[MCPToolAdapter] = []
        for remote in client.list_tools():
            remote_name = str(remote.get("name", ""))
            if not remote_name:
                continue
            full_name = f"mcp__{name}__{remote_name}"
            adapter = MCPToolAdapter(
                client,
                full_name,
                description=str(remote.get("description", "") or f"MCP tool from server {name}"),
                parameters=remote.get("inputSchema", remote.get("parameters", {})),
            )
            self._tools[full_name] = adapter
            adapters.append(adapter)
        return adapters

    def add_to_registry(self, registry: ToolRegistry) -> int:
        for tool in self._tools.values():
            registry.register(tool)
        return len(self._tools)

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": tool.name, "description": tool.description} for tool in self._tools.values()]

    def close(self) -> None:
        for client in self._clients.values():
            client.close()
        self._clients.clear()
        self._tools.clear()
