"""Provider-agnostic message, result and streaming contracts."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pix.errors import ProviderError


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(slots=True)
class ToolCall:
    """A model-requested function invocation."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass(slots=True)
class ChatMessage:
    """A conversation message in the provider-neutral protocol."""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None

    @classmethod
    def system(cls, content: str) -> ChatMessage:
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> ChatMessage:
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(cls, content: str = "", tool_calls: list[ToolCall] | None = None) -> ChatMessage:
        return cls(role=Role.ASSISTANT, content=content, tool_calls=tool_calls or [])

    @classmethod
    def tool(cls, tool_call_id: str, content: str, name: str | None = None) -> ChatMessage:
        return cls(role=Role.TOOL, content=content, tool_call_id=tool_call_id, name=name)


@dataclass(slots=True)
class Usage:
    """Token usage with optional, explicit cost information."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    estimated_cost_usd: float | None = None
    model: str | None = None

    def to_dict(self) -> dict[str, int | float | str | None]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "model": self.model,
        }


@dataclass(slots=True)
class LLMResult:
    """A completed provider generation."""

    message: ChatMessage
    usage: Usage
    finish_reason: str = "stop"
    latency_seconds: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StreamEvent:
    """An incremental text or tool-call delta."""

    kind: Literal["text_delta", "tool_call_delta", "done", "error"]
    text: str = ""
    tool_call_id: str | None = None
    tool_name: str | None = None
    arguments_delta: str = ""
    error: str | None = None
    usage: Usage | None = None
    message: ChatMessage | None = None


class LLMProvider(ABC):
    """Interface implemented by every supported model backend."""

    name: str = "base"

    @abstractmethod
    def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        """Run one model generation."""

    @abstractmethod
    def generate_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
    ) -> Iterator[StreamEvent]:
        """Yield incremental text and tool-call deltas."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate token count without requiring a provider-specific SDK."""

    @abstractmethod
    def normalize_response(self, result: LLMResult) -> LLMResult:
        """Normalize a backend-specific result into the shared contract."""

    @abstractmethod
    def close(self) -> None:
        """Release any transport resources held by the provider."""

    def __enter__(self) -> LLMProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def collect_stream(events: Iterator[StreamEvent]) -> LLMResult:
    """Build a completed :class:`LLMResult` from an incremental event stream."""

    text_parts: list[str] = []
    tool_calls: dict[str, dict[str, object]] = {}
    usage = Usage()
    finish_reason = "stop"
    final_message: ChatMessage | None = None

    for event in events:
        if event.kind == "error":
            raise ProviderError(event.error or "Provider stream failed")
        if event.kind == "text_delta" and event.text:
            text_parts.append(event.text)
        elif event.kind == "tool_call_delta":
            call_id = event.tool_call_id or "call_0"
            call = tool_calls.setdefault(call_id, {"id": call_id, "name": "", "arguments": ""})
            if event.tool_name:
                call["name"] = event.tool_name
            call["arguments"] = str(call["arguments"]) + event.arguments_delta
        elif event.kind == "done":
            if event.usage is not None:
                usage = event.usage
            if event.message is not None:
                final_message = event.message
            break

    if final_message is not None:
        return LLMResult(message=final_message, usage=usage, finish_reason=finish_reason)

    parsed_calls: list[ToolCall] = []
    for raw_call in tool_calls.values():
        arguments_text = str(raw_call.get("arguments") or "").strip() or "{}"
        try:
            arguments = json.loads(arguments_text)
        except json.JSONDecodeError:
            arguments = {"_raw": arguments_text}
        parsed_calls.append(
            ToolCall(
                id=str(raw_call.get("id") or f"call_{len(parsed_calls)}"),
                name=str(raw_call.get("name") or ""),
                arguments=arguments,
            )
        )
    return LLMResult(
        message=ChatMessage.assistant(content="".join(text_parts), tool_calls=parsed_calls),
        usage=usage,
        finish_reason=finish_reason,
    )
