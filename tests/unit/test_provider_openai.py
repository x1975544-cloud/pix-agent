from __future__ import annotations

import json

import httpx
from pix.providers.base import ChatMessage, Role, ToolCall
from pix.providers.openai import OpenAIProvider


def _handler(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["instructions"]
        assert body["tools"]
        response = {
            "id": "resp_1",
            "model": "gpt-test",
            "status": "completed",
            "usage": {"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "read_file",
                    "arguments": json.dumps({"path": "app.py"}),
                }
            ],
        }
        return httpx.Response(200, json=response)

    return handler


def test_openai_provider_parses_tool_calls():
    client = httpx.Client(transport=httpx.MockTransport(_handler({})))
    provider = OpenAIProvider("sk-test-1234567890", client=client)
    result = provider.generate(
        [ChatMessage.system("You are PiX"), ChatMessage.user("Read a file")],
        [{"type": "function", "name": "read_file", "parameters": {}}],
    )
    assert result.message.tool_calls == [ToolCall(id="call_1", name="read_file", arguments={"path": "app.py"})]
    assert result.usage.input_tokens == 12
    assert result.message.role == Role.ASSISTANT
    provider.close()


def test_openai_provider_encodes_tool_output_messages():
    provider = OpenAIProvider("sk-test-1234567890", client=httpx.Client())
    messages = [
        ChatMessage.user("hello"),
        ChatMessage.assistant(tool_calls=[ToolCall(id="call_1", name="read_file", arguments={"path": "a.py"})]),
        ChatMessage.tool("call_1", "content here", name="read_file"),
    ]
    body = provider._build_request(messages, tools=[], model=None)
    assert body["input"][1]["type"] == "function_call"
    assert body["input"][1]["call_id"] == "call_1"
    assert body["input"][2]["type"] == "function_call_output"
    provider.close()
