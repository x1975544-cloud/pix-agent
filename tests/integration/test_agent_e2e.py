from __future__ import annotations

import json

import pytest
from pix.agent.executor import AgentExecutor
from pix.agent.state import AgentStatus
from pix.config.settings import Settings
from pix.providers.base import ChatMessage, ToolCall
from tests.conftest import ScriptedProvider


@pytest.mark.integration
def test_executor_end_to_end_with_scripted_provider(tmp_path):
    (tmp_path / "app.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    (tmp_path / "test_app.py").write_text(
        "from app import hello\n\ndef test_hello():\n    assert hello() == 'hi'\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")

    plan = {
        "title": "Inspect demo",
        "summary": "Look at the demo project.",
        "steps": [
            {"title": "Inspect", "description": "List repository files."},
            {"title": "Report", "description": "Explain findings."},
        ],
    }
    provider = ScriptedProvider(
        [
            ChatMessage.assistant(json.dumps(plan)),
            ChatMessage.assistant(tool_calls=[ToolCall(id="call_1", name="list_directory", arguments={"path": "."})]),
            ChatMessage.assistant("The repository is a small Python demo."),
        ]
    )
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{tmp_path}/agent.db",
        workspace=str(tmp_path),
        max_iterations=5,
        log_level="ERROR",
    )
    executor = AgentExecutor(settings, provider=provider)
    result = executor.execute(
        "Explain this repository",
        workspace=tmp_path,
        auto_verify=False,
    )
    assert result.status == AgentStatus.SUCCESS
    assert result.state.plan is not None
    assert len(result.state.observations) == 1
    session = executor.get_session(result.trace_id or "")
    assert session.status == "success"
    assert executor.trace(result.trace_id or "")
