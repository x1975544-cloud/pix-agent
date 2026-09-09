"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from pix.errors import ProviderError
from pix.providers.base import (
    ChatMessage,
    LLMProvider,
    LLMResult,
    StreamEvent,
    Usage,
)


class ScriptedProvider(LLMProvider):
    """Provider that replays scripted messages and tool calls."""

    name = "scripted"

    def __init__(self, responses: list[ChatMessage], *, usage: Usage | None = None) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.usage = usage or Usage(input_tokens=11, output_tokens=7, total_tokens=18)

    def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        self.calls.append(
            {
                "messages": [
                    message.model_dump() if hasattr(message, "model_dump") else str(message) for message in messages
                ],
                "tools": tools,
                "model": model,
            }
        )
        if not self.responses:
            raise ProviderError("Scripted provider ran out of responses")
        message = self.responses.pop(0)
        return LLMResult(message=message, usage=self.usage, finish_reason="stop")

    def generate_stream(
        self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None, *, model: str | None = None
    ) -> Iterator[StreamEvent]:
        if not self.responses:
            raise ProviderError("Scripted provider ran out of responses")
        message = self.responses.pop(0)
        if message.content:
            yield StreamEvent(kind="text_delta", text=message.content)
        yield StreamEvent(kind="done", message=message, usage=self.usage)

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4) if text else 0

    def normalize_response(self, result: LLMResult) -> LLMResult:
        return result

    def close(self) -> None:
        pass


@pytest.fixture
def scripted_provider() -> ScriptedProvider:
    return ScriptedProvider([])
