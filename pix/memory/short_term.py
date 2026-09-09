"""Session-scoped working memory built from live agent messages."""

from __future__ import annotations

from dataclasses import dataclass, field

from pix.providers.base import ChatMessage


@dataclass(slots=True)
class ShortTermMemory:
    """Small ring buffer for facts surfaced during the current session."""

    session_id: str
    capacity: int = 60
    entries: list[str] = field(default_factory=list)

    def remember(self, text: str) -> None:
        self.entries.append(text)
        if len(self.entries) > self.capacity:
            self.entries = self.entries[-self.capacity :]

    def remember_message(self, message: ChatMessage) -> None:
        if message.content:
            self.remember(f"{message.role.value}: {message.content[:1000]}")

    def recall(self, limit: int = 10) -> list[str]:
        return self.entries[-limit:]

    def reset(self) -> None:
        self.entries.clear()
