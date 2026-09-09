from __future__ import annotations

from pix.agent.loop import AgentLoop, LoopOptions
from pix.agent.state import AgentState
from pix.context.manager import ContextManager
from pix.errors import AgentLoopError
from pix.providers.base import ChatMessage, ToolCall
from pix.security import Workspace
from pix.tools.filesystem import ListDirectoryTool
from pix.tools.registry import ToolRegistry
from tests.conftest import ScriptedProvider


def test_agent_loop_runs_tool_then_finishes(tmp_path):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    provider = ScriptedProvider(
        [
            ChatMessage.assistant(tool_calls=[ToolCall(id="call_1", name="list_directory", arguments={"path": "."})]),
            ChatMessage.assistant("Analysis complete."),
        ]
    )
    state = AgentState(session_id="sess", task="Inspect repo", workspace=tmp_path)
    state.add_message(ChatMessage.user("Inspect repo"))
    registry = ToolRegistry([ListDirectoryTool(Workspace(tmp_path))])
    loop = AgentLoop(
        provider,
        registry,
        ContextManager(4000),
        options=LoopOptions(max_iterations=3),
        system_prompt="Be a coding agent.",
    )
    result = loop.run(state)
    assert result.final_answer == "Analysis complete."
    assert result.iteration == 2
    assert len(result.observations) == 1
    assert provider.calls[1]["tools"]


def test_agent_loop_max_iterations(tmp_path):
    provider = ScriptedProvider(
        [
            ChatMessage.assistant(tool_calls=[ToolCall(id=f"c{index}", name="missing", arguments={})])
            for index in range(2)
        ]
    )
    state = AgentState(session_id="sess", task="Loop", workspace=tmp_path, max_iterations=2)
    state.add_message(ChatMessage.user("Loop"))
    loop = AgentLoop(
        provider,
        ToolRegistry([]),
        ContextManager(4000),
        options=LoopOptions(max_iterations=2),
        system_prompt="System",
    )
    try:
        loop.run(state)
    except AgentLoopError:
        pass
    else:
        raise AssertionError("Expected AgentLoopError")


def test_agent_loop_unknown_tool_is_observation(tmp_path):
    provider = ScriptedProvider(
        [
            ChatMessage.assistant(tool_calls=[ToolCall(id="c1", name="no_such_tool", arguments={})]),
            ChatMessage.assistant("done"),
        ]
    )
    state = AgentState(session_id="sess", task="Loop", workspace=tmp_path)
    state.add_message(ChatMessage.user("Loop"))
    loop = AgentLoop(
        provider,
        ToolRegistry([]),
        ContextManager(4000),
        options=LoopOptions(max_iterations=2),
        system_prompt="System",
    )
    result = loop.run(state)
    assert result.observations[0].success is False
    assert "Unknown tool" in (result.observations[0].error or "")
