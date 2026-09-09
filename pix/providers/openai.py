"""OpenAI provider backed by the Responses API.

The provider is deliberately transport-light: it speaks JSON over ``httpx``
to ``/responses`` and translates between the provider-neutral
:class:`ChatMessage` protocol and Responses input/output items. No SDK is
required and no credential is logged.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

import httpx

from pix.errors import ProviderError
from pix.providers.base import (
    ChatMessage,
    LLMProvider,
    LLMResult,
    Role,
    StreamEvent,
    ToolCall,
    Usage,
)


class OpenAIProvider(LLMProvider):
    """Responses API implementation of :class:`LLMProvider`."""

    name = "openai-responses"

    def __init__(
        self,
        api_key: str | None,
        *,
        api_base: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError(
                "OPENAI_API_KEY is not configured. Set it in the environment or .env before running agents."
            )
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def count_tokens(self, text: str) -> int:
        """Use the same conservative approximation as the context manager."""

        if not text:
            return 0
        return max(1, len(text) // 4)

    def normalize_response(self, result: LLMResult) -> LLMResult:
        """Ensure a Responses result has the shared finish-reason vocabulary."""

        if result.finish_reason not in {"stop", "length", "tool_calls", "content_filter", "error"}:
            result.finish_reason = "stop"
        return result

    def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        started = time.perf_counter()
        body = self._build_request(messages, tools, model=model, temperature=temperature)
        try:
            response = self._client.post(f"{self.api_base}/responses", json=body)
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI request failed: {exc.__class__.__name__}: {exc}") from exc
        if response.is_error:
            raise ProviderError(self._format_error(response))
        payload = response.json()
        message, usage = self._parse_response(payload)
        latency = time.perf_counter() - started
        return self.normalize_response(
            LLMResult(
            message=message,
            usage=usage,
            finish_reason=str(payload.get("status", "completed")),
            latency_seconds=latency,
            raw={"id": payload.get("id"), "model": payload.get("model")},
            )
        )

    def generate_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
    ) -> Iterator[StreamEvent]:
        body = self._build_request(messages, tools, model=model, stream=True)
        tool_names: dict[str, str] = {}
        final_usage: Usage | None = None
        try:
            with self._client.stream("POST", f"{self.api_base}/responses", json=body) as response:
                if response.is_error:
                    yield StreamEvent(kind="error", error=self._format_error(response))
                    return
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line.removeprefix("data:").strip()
                    if raw == "[DONE]":
                        break
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    event_type = event.get("type", "")
                    if event_type == "response.output_text.delta":
                        yield StreamEvent(kind="text_delta", text=event.get("delta", ""))
                    elif event_type == "response.function_call_arguments.delta":
                        item_id = str(event.get("item_id") or "")
                        yield StreamEvent(
                            kind="tool_call_delta",
                            tool_call_id=item_id,
                            arguments_delta=event.get("delta", ""),
                        )
                    elif event_type == "response.function_call_arguments.done":
                        item_id = str(event.get("item_id") or "")
                        tool_names[item_id] = str(event.get("name") or "")
                        yield StreamEvent(
                            kind="tool_call_delta",
                            tool_call_id=item_id,
                            tool_name=tool_names[item_id],
                            arguments_delta="",
                        )
                    elif event_type == "response.completed":
                        raw_usage = event.get("response", {}).get("usage") or {}
                        final_usage = Usage(
                            input_tokens=int(raw_usage.get("input_tokens") or 0),
                            output_tokens=int(raw_usage.get("output_tokens") or 0),
                            total_tokens=int(raw_usage.get("total_tokens") or 0),
                            cached_input_tokens=int(
                                raw_usage.get("input_tokens_details", {}).get("cached_tokens") or 0
                            ),
                            model=event.get("response", {}).get("model") or model or self.model,
                        )
        except httpx.HTTPError as exc:
            yield StreamEvent(kind="error", error=str(exc))
            return
        yield StreamEvent(kind="done", usage=final_usage)

    def _build_request(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None,
        *,
        model: str | None,
        temperature: float | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        instructions: list[str] = []
        input_items: list[dict[str, Any]] = []
        for message in messages:
            if message.role == Role.SYSTEM:
                instructions.append(message.content)
                continue
            if message.role == Role.USER:
                input_items.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": message.content}],
                    }
                )
            elif message.role == Role.ASSISTANT:
                if message.content:
                    input_items.append(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": message.content}],
                        }
                    )
                for call in message.tool_calls:
                    input_items.append(
                        {
                            "type": "function_call",
                            "id": f"fc_{call.id}",
                            "call_id": call.id,
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            "status": "completed",
                        }
                    )
            elif message.role == Role.TOOL:
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": message.tool_call_id or "",
                        "output": message.content,
                    }
                )
        body: dict[str, Any] = {
            "model": model or self.model,
            "input": input_items,
            "store": False,
            "stream": stream,
            "parallel_tool_calls": True,
        }
        if instructions:
            body["instructions"] = "\n\n".join(instructions)
        if tools:
            body["tools"] = tools
        if temperature is not None:
            body["temperature"] = temperature
        return body

    def _parse_response(self, payload: dict[str, Any]) -> tuple[ChatMessage, Usage]:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for item in payload.get("output", []):
            item_type = item.get("type")
            if item_type == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text" and part.get("text"):
                        text_parts.append(str(part["text"]))
            elif item_type == "function_call":
                arguments_raw = item.get("arguments") or "{}"
                try:
                    arguments: dict[str, Any] = json.loads(arguments_raw)
                except json.JSONDecodeError:
                    arguments = {"_raw": arguments_raw}
                call_id = str(item.get("call_id") or item.get("id") or f"call_{len(tool_calls)}")
                tool_calls.append(ToolCall(id=call_id, name=str(item.get("name", "")), arguments=arguments))

        raw_usage = payload.get("usage") or {}
        input_tokens = int(raw_usage.get("input_tokens") or raw_usage.get("prompt_tokens") or 0)
        output_tokens = int(raw_usage.get("output_tokens") or raw_usage.get("completion_tokens") or 0)
        total = int(raw_usage.get("total_tokens") or input_tokens + output_tokens)
        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            cached_input_tokens=int(raw_usage.get("input_tokens_details", {}).get("cached_tokens") or 0),
            model=payload.get("model"),
        )
        message = ChatMessage.assistant(content="\n".join(text_parts), tool_calls=tool_calls)
        return message, usage

    @staticmethod
    def _format_error(response: httpx.Response) -> str:
        try:
            detail = response.json()
            message = detail.get("error", {}).get("message", detail)
        except (ValueError, AttributeError):
            message = response.text[:1000]
        return f"OpenAI API error {response.status_code}: {message}"
