"""Tool registry that exposes provider-neutral schemas to LLMs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, TypeAlias

from pix.tools.base import Tool, ToolNotFoundError

ToolList: TypeAlias = list[Tool]
ToolSchemaList: TypeAlias = list[dict[str, Any]]


class ToolRegistry:
    """Register, remove and resolve tools by name."""

    def __init__(self, tools: Iterable[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> Tool | None:
        return self._tools.pop(name, None)

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    def list(self) -> ToolList:
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        return name in self._tools

    def schemas(self) -> ToolSchemaList:
        """Return schemas in the OpenAI-compatible tool format."""

        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]
