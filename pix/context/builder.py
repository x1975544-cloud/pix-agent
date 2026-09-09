"""Assemble a context from prioritized, sectioned content."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import IntEnum

from pix.context.window import Budget, estimate_tokens
from pix.providers.base import ChatMessage


class ContextPriority(IntEnum):
    SYSTEM = 0
    TASK = 1
    PLAN = 2
    CURRENT_STATE = 3
    RELEVANT_CODE = 4
    RECENT_RESULTS = 5
    MEMORY = 6
    OLD_HISTORY = 7


@dataclass(slots=True)
class ContextSection:
    """Named, prioritized text content for a system prompt."""

    key: str
    content: str
    priority: ContextPriority = ContextPriority.SYSTEM


@dataclass(slots=True)
class BuiltContext:
    """Final prompt context plus bookkeeping for observability."""

    system_prompt: str
    messages: list[ChatMessage] = field(default_factory=list)
    token_estimate: int = 0
    sections: list[ContextSection] = field(default_factory=list)
    truncated: bool = False
    compression_summary: str = ""


class ContextBuilder:
    """Order sections by priority and enforce a token budget."""

    def __init__(self, budget_tokens: int) -> None:
        self.budget_tokens = budget_tokens

    def build(
        self,
        *,
        base_system: str,
        task: str,
        conversation: list[ChatMessage],
        extra_sections: list[ContextSection] | None = None,
        recent_max_messages: int = 40,
    ) -> BuiltContext:
        sections = self._prioritize_sections(
            [
                ContextSection("system", base_system, ContextPriority.SYSTEM),
                ContextSection("task", f"Current task:\n{task}", ContextPriority.TASK),
                *(extra_sections or []),
            ]
        )
        system_text = "\n\n".join(section.content for section in sections if section.content)
        budget = Budget(self.budget_tokens)
        budget.reserve(estimate_tokens(system_text))

        # Keep the newest conversation within the budget, then compression will
        # summarize the rest on a subsequent call.
        selected: list[ChatMessage] = []
        truncated = False
        for message in reversed(conversation):
            estimate = estimate_tokens(message.content) + len(message.tool_calls) * 30
            if budget.remaining < estimate and selected:
                truncated = True
                break
            if budget.reserve(estimate) < estimate:
                message_text = message.content[: max(0, budget.remaining * 4)]
                budget.reserve(estimate_tokens(message_text))
                if message_text:
                    selected.append(replace(message, content=message_text))
                truncated = True
                break
            selected.append(message)
            if len(selected) >= recent_max_messages:
                truncated = True
                break
        messages = list(reversed(selected))
        return BuiltContext(
            system_prompt=system_text,
            messages=messages,
            token_estimate=estimate_tokens(system_text) + sum(estimate_tokens(message.content) for message in messages),
            sections=sections,
            truncated=truncated,
        )

    @staticmethod
    def _prioritize_sections(sections: list[ContextSection]) -> list[ContextSection]:
        # Stable ordering: same-priority sections keep insertion order.
        return sorted(sections, key=lambda section: section.priority.value)
