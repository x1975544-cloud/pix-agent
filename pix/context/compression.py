"""Budget-aware context compression that summarizes rather than hard-truncates."""

from __future__ import annotations

from collections import Counter

from pix.context.window import estimate_tokens, truncate_to_tokens
from pix.providers.base import ChatMessage, Role


class ContextCompressor:
    """Compress older history into compact facts while preserving the tail."""

    def __init__(self, keep_recent_messages: int = 12) -> None:
        self.keep_recent_messages = keep_recent_messages

    def compress(self, messages: list[ChatMessage], summary_token_limit: int = 800) -> tuple[list[ChatMessage], str]:
        """Return a compressed message list and a human-readable summary."""

        if len(messages) <= self.keep_recent_messages:
            return messages, ""
        recent = messages[-self.keep_recent_messages :]
        old = messages[: -self.keep_recent_messages]
        summary = self._extract_facts(old)
        if estimate_tokens(summary) > summary_token_limit:
            summary = truncate_to_tokens(summary, summary_token_limit)
        if summary:
            recent = [ChatMessage.system(f"Compressed prior context:\n{summary}"), *recent]
        return recent, summary

    @staticmethod
    def _extract_facts(messages: list[ChatMessage]) -> str:
        role_counts = Counter(message.role.value for message in messages)
        tool_calls = sum(len(message.tool_calls) for message in messages)
        user_notes = [message.content.strip() for message in messages if message.role == Role.USER and message.content]
        tool_summaries: list[str] = []
        for message in reversed(messages):
            if message.role == Role.TOOL:
                content = message.content[:400].replace("\n", " ")
                tool_summaries.append(f"- {message.name or 'tool'}: {content}")
                if len(tool_summaries) >= 5:
                    break
        lines = [
            f"Earlier context had {role_counts.get('user', 0)} user, "
            f"{role_counts.get('assistant', 0)} assistant and {role_counts.get('tool', 0)} tool messages "
            f"({tool_calls} tool calls).",
        ]
        if user_notes:
            lines.append("User notes: " + "; ".join(note[:180] for note in user_notes[-3:]))
        lines.extend(tool_summaries)
        return "\n".join(lines)
