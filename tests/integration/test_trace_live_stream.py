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


class DisconnectAfterFirstHistoryChunkRequest(FakeRequest):
    """Disconnects as soon as one stored history event has been yielded."""

    def __init__(self, agent: Agent) -> None:
        super().__init__(agent)
        self.chunks = 0

    async def is_disconnected(self) -> bool:
        return self.chunks > 0


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


def test_event_bus_slow_subscriber_does_not_block_publisher():
    bus = EventBus(max_queue_size=1)
    slow_subscriber = bus.subscribe()

    def publish_events() -> None:
        for index in range(2000):
            bus.publish("TOOL_CALL", {"index": index}, session_id="sess_slow")

    publisher = threading.Thread(target=publish_events, name="event-bus-publisher", daemon=True)
    publisher.start()
    publisher.join(timeout=2)

    assert not publisher.is_alive(), "A full subscriber must not block the agent event bus"
    assert bus.subscriber_count == 1
    assert slow_subscriber.qsize() == 1
    assert slow_subscriber.get_nowait().payload == {"index": 1999}


def test_event_bus_tolerates_concurrent_subscribe_publish_unsubscribe():
    bus = EventBus(max_queue_size=16)
    errors: list[BaseException] = []

    def publish_events() -> None:
        try:
            for index in range(1000):
                bus.publish("TOKEN", {"index": index}, session_id="sess_concurrent")
        except BaseException as exc:  # noqa: BLE001 - kept for test diagnostics
            errors.append(exc)

    publisher = threading.Thread(target=publish_events, name="event-bus-concurrent", daemon=True)
    publisher.start()
    for _ in range(200):
        subscriber = bus.subscribe()
        bus.unsubscribe(subscriber)
    publisher.join(timeout=2)

    assert not publisher.is_alive()
    assert not errors
    assert bus.subscriber_count == 0


def test_live_trace_stream_cleans_subscriber_when_consumer_is_cancelled():
    bus = EventBus()
    agent = SimpleNamespace(
        executor=SimpleNamespace(event_bus=bus),
        session=lambda _session_id: SimpleNamespace(status="pending"),
        trace=lambda _session_id: [],
    )

    async def main() -> None:
        response = await stream_trace(FakeRequest(agent), "sess_pending")
        consumer = asyncio.create_task(response.body_iterator.__anext__())
        await asyncio.sleep(0.35)
        assert bus.subscriber_count == 1
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        assert bus.subscriber_count == 0

    asyncio.run(main())


def test_live_trace_stream_stops_replay_after_disconnect():
    bus = EventBus()
    history = [
        {
            "id": "history-1",
            "type": "SESSION_STARTED",
            "timestamp": "2026-09-09T00:00:00Z",
            "payload": {},
            "duration_ms": None,
            "metadata": {},
        },
        {
            "id": "history-2",
            "type": "PLAN_CREATED",
            "timestamp": "2026-09-09T00:00:01Z",
            "payload": {},
            "duration_ms": None,
            "metadata": {},
        },
        {
            "id": "history-3",
            "type": "AGENT_FINISHED",
            "timestamp": "2026-09-09T00:00:02Z",
            "payload": {},
            "duration_ms": None,
            "metadata": {},
        },
    ]
    agent = SimpleNamespace(
        executor=SimpleNamespace(event_bus=bus),
        session=lambda _session_id: SimpleNamespace(status="success"),
        trace=lambda _session_id: history,
    )
    request = DisconnectAfterFirstHistoryChunkRequest(agent)

    async def consume() -> None:
        response = await stream_trace(request, "sess_history")
        async for _chunk in response.body_iterator:
            request.chunks += 1

    asyncio.run(consume())

    assert request.chunks == 1
    assert bus.subscriber_count == 0
