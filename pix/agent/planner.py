"""Task planner that produces structured plans without executing them."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pix.agent.state import Plan, PlanStep
from pix.analysis.repository import RepositoryContext
from pix.errors import ProviderError
from pix.providers.base import ChatMessage, LLMProvider

logger = logging.getLogger(__name__)


class Planner:
    """Convert a user task and repository summary into a Plan."""

    def __init__(self, provider: LLMProvider, *, model: str | None = None) -> None:
        self.provider = provider
        self.model = model

    def plan(self, task: str, repository: RepositoryContext | None = None) -> Plan:
        prompt = self._plan_prompt(task, repository)
        try:
            result = self.provider.generate(
                [
                    ChatMessage.system(
                        "You are a software engineering planner. Return only valid JSON matching the requested schema."
                    ),
                    ChatMessage.user(prompt),
                ],
                model=self.model,
            )
        except ProviderError as exc:
            raise ProviderError(f"Planning failed: {exc}") from exc
        payload = self._parse_plan_json(result.message.content)
        return self._validate_plan(payload)

    @staticmethod
    def _plan_prompt(task: str, repository: RepositoryContext | None) -> str:
        repo = repository.to_dict() if repository else {}
        return f"""Create a concise execution plan for the following coding task.

Task: {task}

Repository signals:
{json.dumps(repo, ensure_ascii=False, indent=2)}

Return JSON with this exact shape:
{{
  "title": "short title",
  "summary": "one or two sentences",
  "steps": [
    {{"title": "step title", "description": "what to inspect or change", "commands": ["optional command"]}}
  ]
}}

Keep plans under 12 steps. Prefer small, verifiable edits. Include repository
analysis, implementation, tests and git operations when they are appropriate
for the task."""

    @staticmethod
    def _parse_plan_json(content: str) -> dict[str, Any]:
        text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        candidate = fenced.group(1) if fenced else text
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Planner returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Planner JSON payload must be an object")
        return payload

    @classmethod
    def _validate_plan(cls, payload: dict[str, Any]) -> Plan:
        title = str(payload.get("title") or "Untitled plan")
        summary = str(payload.get("summary") or "")
        steps: list[PlanStep] = []
        for index, raw_step in enumerate(payload.get("steps", []), start=1):
            if not isinstance(raw_step, dict):
                continue
            commands = raw_step.get("commands") or []
            steps.append(
                PlanStep(
                    title=str(raw_step.get("title") or f"Step {index}"),
                    description=str(raw_step.get("description") or ""),
                    commands=[str(command) for command in commands if isinstance(command, str)],
                )
            )
        if not steps:
            raise ProviderError("Planner returned a plan with no steps")
        return Plan(title=title, summary=summary, steps=steps[:12])

    @staticmethod
    def fallback_plan(task: str) -> Plan:
        """Deterministic baseline plan used by tests or offline tooling."""

        return Plan(
            title="Standard engineering loop",
            summary=f"Apply the standard plan, reason, act, observe, verify and commit workflow to: {task}",
            steps=[
                PlanStep(
                    title="Analyze repository",
                    description="Inspect manifests, entrypoints, tests and existing code.",
                ),
                PlanStep(
                    title="Locate relevant code",
                    description="Search and read code related to the task.",
                ),
                PlanStep(
                    title="Design the change",
                    description="Choose a minimal edit consistent with the repository.",
                ),
                PlanStep(
                    title="Implement the change",
                    description="Write or update source and test files.",
                ),
                PlanStep(
                    title="Run tests and checks",
                    description="Run the detected test command and fix failures.",
                ),
                PlanStep(
                    title="Review the diff",
                    description="Inspect git diff and confirm only intended changes.",
                ),
                PlanStep(
                    title="Commit when complete",
                    description="Create a concise conventional commit.",
                ),
            ],
        )
