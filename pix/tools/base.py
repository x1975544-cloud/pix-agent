"""Unified tool contract used by local tools, registry and MCP adapters."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pix.errors import ToolError


@dataclass(slots=True)
class ToolResult:
    """Result of a tool execution, always serializable for model observations."""

    success: bool
    output: Any = None
    error: str | None = None
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Render the result as compact, model-safe text."""

        body = {"success": False, "error": self.error} if self.error else {"success": True, "result": self.output}
        body["duration_seconds"] = round(self.duration_seconds, 4)
        return json.dumps(body, ensure_ascii=False, default=str)


class Tool(ABC):
    """Base class for every tool exposed to a model."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    timeout_seconds: float = 60.0
    dangerous: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ToolError("Tool subclasses must define a name")

    @abstractmethod
    def run(self, arguments: dict[str, Any]) -> Any:
        """Execute the tool body; callers wrap exceptions into ToolResult."""

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        try:
            output = self.run(arguments)
        except Exception as exc:  # noqa: BLE001 - tool boundary must stay stable
            duration = time.perf_counter() - started
            return ToolResult(success=False, error=str(exc), duration_seconds=duration)
        duration = time.perf_counter() - started
        return ToolResult(success=True, output=output, duration_seconds=duration)


class ToolNotFoundError(KeyError):
    """Raised when the registry has no tool with the requested name."""
