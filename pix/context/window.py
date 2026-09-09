"""Token estimation and context-window helpers."""

from __future__ import annotations

from dataclasses import dataclass


def estimate_tokens(text: str) -> int:
    """Cheap deterministic token estimate: roughly four characters per token."""

    if not text:
        return 0
    return max(1, len(text) // 4)


def truncate_from_start(text: str, max_chars: int) -> str:
    """Truncate from the start while preserving the newest tail of a message."""

    if len(text) <= max_chars:
        return text
    return "…[truncated]…\n" + text[-(max_chars - 20) :]


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n…[truncated middle]…\n{tail}"


@dataclass(slots=True)
class Budget:
    """Token budget accounting for one context build."""

    total: int
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.used)

    def reserve(self, tokens: int) -> int:
        allowed = min(tokens, self.remaining)
        self.used += allowed
        return allowed
