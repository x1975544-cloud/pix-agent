from __future__ import annotations

import asyncio
import json
import queue
import threading
from types import SimpleNamespace
from typing import Any

import pytest
from pix.agent.agent import Agent
from pix.api.routes.traces import stream_trace
from pix.config.settings import Settings
from pix.providers.base import ChatMessage
from pix.tracing.bus import EventBus
from pydantic import SecretStr
from tests.conftest import ScriptedProvider


class FakeRequest:
    """Minimal Request facade used by :func:`stream_trace` in tests."""

    def __init__(self, agent: Agent) -> None:
        self.app = SimpleNamespace(state=SimpleNamespace(agent=agent))

    async def is_disconnected(self) -> bool:
        return False


class DisconnectedRequest(FakeRequest):
    async def is_disconnected(self) -> bool:
        return True


class GatedScriptedProvider(ScriptedProvider):
    """Scripted provider that pauses before the first planner request."""

    def __init__(self, responses: list[ChatMessage], *, gate: threading.Event) -> None:
        super().__init__(responses)
        self.gate = gate
        self.planner_started = False

    def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> Any:
        if not self.planner_started:
            self.planner_started = True
            if not self.gate.wait(timeout=10):
                raise TimeoutError("Test did not release the gated provider")
        return super().generate(messages, tools, model=model, temperature=temperature)


@pytest.mark.integration
def test_live_trace_stream_receives_agent_run_events(tmp_path):
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    gate = threading.Event()
    plan = {
        "title": "Inspect demo",
        "summary": "Inspect the repository.",
        "steps": [{"title": "Inspect", "description": "Read the project."}],
    }
    provider = GatedScriptedProvider(
        [ChatMessage.assistant(json.dumps(plan)), ChatMessage.assistant("Done.")],
        gate=gate,
    )
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        api_key=SecretStr(""),
        database_url=f"sqlite:///{tmp_path}/trace.db",
        workspace=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        log_level="ERROR",
    )
    agent = Agent(settings, provider=provider)
    errors: list[BaseException] = []

    def run_agent() -> None:
        try:
            agent.run("Inspect the repository", workspace=tmp_path, auto_verify=False)
        except BaseException as exc:  # noqa: BLE001 - kept for test diagnostics
            errors.append(exc)

    thread = threading.Thread(target=run_agent, name="live-trace-test-run", daemon=True)
    thread.start()
    observer = agent.executor.event_bus.subscribe()
    try:
        started = observer.get(timeout=10)
        assert started.type == "SESSION_STARTED", started.type
        assert started.session_id is not None
        session_id = started.session_id
        observer.get(timeout=10)
    except queue.Empty:
        pytest.fail("Agent run did not publish enough trace events")
    finally:
        agent.executor.event_bus.unsubscribe(observer)

    first_chunk_seen = asyncio.Event()
    live_events: list[str] = []

    async def consume_stream() -> None:
        response = await stream_trace(FakeRequest(agent), session_id)
        async for chunk in response.body_iterator:
            if not first_chunk_seen.is_set():
                first_chunk_seen.set()
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for raw_line in text.splitlines():
                if not raw_line.startswith("event: "):
                    continue
                live_events.append(raw_line.removeprefix("event: "))

    async def main() -> None:
        consumer = asyncio.create_task(consume_stream())
        await asyncio.wait_for(first_chunk_seen.wait(), timeout=5)
        gate.set()
        await asyncio.wait_for(consumer, timeout=10)

    try:
        asyncio.run(main())
    finally:
        gate.set()
        thread.join(timeout=10)

    assert "plan_created" in live_events, (live_events, errors)
    assert "agent_finished" in live_events or "completed" in live_events, (live_events, errors)
    assert agent.executor.event_bus.subscriber_count == 0
    assert not errors, errors


@pytest.mark.integration
def test_stream_unsubscribes_on_disconnect():
    bus = EventBus()
    agent = SimpleNamespace(
        executor=SimpleNamespace(event_bus=bus),
        session=lambda _session_id: SimpleNamespace(status="pending"),
        trace=lambda _session_id: [],
    )

    async def consume() -> None:
        response = await stream_trace(DisconnectedRequest(agent), "sess_pending")
        async for _chunk in response.body_iterator:
            pass

    asyncio.run(consume())
    assert bus.subscriber_count == 0
