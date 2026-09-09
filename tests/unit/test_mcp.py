from __future__ import annotations

from typing import Any

from pix.mcp.adapter import MCPToolAdapter
from pix.mcp.client import MCPClient
from pix.mcp.registry import MCPRegistry
from pix.tools.registry import ToolRegistry


class FakeMCPClient(MCPClient):
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "read_remote",
                "description": "Read remote data",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
            }
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return [{"type": "text", "text": f"remote {arguments.get('id')}"}]

    def close(self) -> None:
        self.started = False


def test_mcp_registry_adapts_tools():
    client = FakeMCPClient()
    mcp = MCPRegistry()
    adapters = mcp.register_server("demo", client)
    assert client.started
    assert adapters[0].name == "mcp__demo__read_remote"
    assert adapters[0].execute({"id": "42"}).success

    registry = ToolRegistry([])
    assert mcp.add_to_registry(registry) == 1
    assert registry.has("mcp__demo__read_remote")

    mcp.close()
    assert not client.started


def test_mcp_adapter_schema():
    adapter = MCPToolAdapter(FakeMCPClient(), "remote", "does work", {"type": "object", "properties": {}})
    assert adapter.name == "remote"
    assert adapter.description == "does work"
