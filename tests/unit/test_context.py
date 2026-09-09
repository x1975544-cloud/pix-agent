from __future__ import annotations

from pix.agent.state import AgentState
from pix.context.compression import ContextCompressor
from pix.context.manager import ContextManager
from pix.providers.base import ChatMessage


def test_context_build_keeps_task_first():
    state = AgentState(session_id="s1", task="Add auth", workspace=__import__("pathlib").Path("."))
    state.add_message(ChatMessage.user("Add auth"))
    built = ContextManager(budget_tokens=1000).build(state)
    assert built.system_prompt
    assert built.messages
    assert built.token_estimate > 0


def test_compressor_summarizes_old_history():
    messages = [ChatMessage.user(f"message {index}") for index in range(20)]
    compressor = ContextCompressor(keep_recent_messages=5)
    result, summary = compressor.compress(messages)
    assert summary
    assert len(result) <= 6


def test_context_truncates_when_budget_small():
    state = AgentState(session_id="s1", task="Task", workspace=__import__("pathlib").Path("."))
    state.add_message(ChatMessage.user("Task"))
    for index in range(20):
        state.add_message(ChatMessage.assistant(f"reasoning {index} " + "x" * 300))
    built = ContextManager(budget_tokens=500).build(state)
    assert built.token_estimate <= 500
