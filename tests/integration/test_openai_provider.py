from __future__ import annotations

import os

import pytest
from pix.agent.agent import Agent
from pix.config.settings import Settings
from pix.providers.base import ChatMessage
from pix.providers.factory import create_provider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PIX_RUN_LIVE_TESTS") != "1",
        reason="Live OpenAI tests require PIX_RUN_LIVE_TESTS=1",
    ),
]


def test_live_openai_provider_returns_text() -> None:
    settings = Settings()
    if not settings.api_key:
        pytest.fail("OPENAI_API_KEY is required for live provider tests")
    provider = create_provider(settings)
    try:
        result = provider.generate([ChatMessage.user("Reply with exactly: OK")], model=settings.model)
    finally:
        provider.close()
    assert result.message.content.strip()


def test_live_openai_agent_uses_repository_tools() -> None:
    settings = Settings()
    if not settings.api_key:
        pytest.fail("OPENAI_API_KEY is required for live provider tests")
    workspace = (__import__("pathlib").Path.cwd() / "examples" / "demo-project").resolve()
    agent = Agent(settings)
    try:
        result = agent.run(
            "Analyze the demo repository and tell me what framework it uses.",
            workspace=workspace,
            auto_verify=False,
        )
    finally:
        agent.close()
    assert result.status.value == "success"
    tool_names = {
        str(event.get("payload", {}).get("name"))
        for event in agent.trace(result.state.session_id)
        if event.get("type") == "TOOL_CALL" and event.get("payload", {}).get("name")
    }
    assert {"list_directory", "read_file"} <= tool_names
