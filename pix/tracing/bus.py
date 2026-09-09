"""In-process pub/sub bus for live trace and streaming events."""

from __future__ import annotations

import queue
import threading
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class LiveEvent:
    """A lightweight event broadcast to active API/CLI consumers."""

    type: str
    session_id: str | None
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    id: str = field(default_factory=lambda: uuid4().hex[:16])
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class EventBus:
    """Thread-safe fan-out bus with bounded subscriber queues."""

    def __init__(self, *, max_queue_size: int = 10_000) -> None:
        self._subscribers: list[queue.Queue[LiveEvent]] = []
        self._max_queue_size = max_queue_size
        self._lock = threading.RLock()

    def subscribe(self) -> queue.Queue[LiveEvent]:
        subscriber: queue.Queue[LiveEvent] = queue.Queue(maxsize=self._max_queue_size)
        with self._lock:
            self._subscribers.append(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[LiveEvent]) -> None:
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def publish(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        session_id: str | None = None,
        event_id: str | None = None,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = LiveEvent(
            type=event_type,
            session_id=session_id,
            payload=payload or {},
            id=event_id or uuid4().hex[:16],
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                # Live consumers must not block an agent run. Drop the oldest
                # event and continue delivering newer progress.
                with suppress(queue.Empty):
                    subscriber.get_nowait()
                with suppress(queue.Full):
                    subscriber.put_nowait(event)


__all__ = ["EventBus", "LiveEvent"]
