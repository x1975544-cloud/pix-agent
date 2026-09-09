"""Benchmark task definitions loaded from JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ValidationRule(BaseModel):
    type: Literal["file_exists", "file_contains", "command"]
    path: str | None = None
    text: str | None = None
    command: str | None = None
    timeout: float = 60.0


class BenchmarkTask(BaseModel):
    """A single reproducible benchmark task."""

    id: str
    category: Literal[
        "repository_navigation",
        "bug_fixing",
        "test_generation",
        "refactoring",
        "feature_implementation",
    ]
    description: str
    workspace: str
    expected_behavior: str
    validation: list[ValidationRule] = Field(default_factory=list)


def load_tasks(directory: str | Path) -> list[BenchmarkTask]:
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"Benchmark task directory not found: {root}")
    tasks: list[BenchmarkTask] = []
    for path in sorted(root.glob("*.json")):
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid benchmark JSON in {path}: {exc}") from exc
        if isinstance(payload, list):
            tasks.extend(BenchmarkTask.model_validate(item) for item in payload)
        else:
            tasks.append(BenchmarkTask.model_validate(payload))
    return tasks
