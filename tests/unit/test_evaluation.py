from __future__ import annotations

import json

from pix.config.settings import Settings
from pix.evaluation.dataset import BenchmarkTask, load_tasks
from pix.evaluation.runner import BenchmarkRunner


def test_load_tasks(tmp_path):
    (tmp_path / "task.json").write_text(
        json.dumps(
            {
                "id": "repo_nav_1",
                "category": "repository_navigation",
                "description": "Find entrypoint",
                "workspace": "examples/demo-project",
                "expected_behavior": "report entrypoint",
                "validation": [{"type": "file_exists", "path": "app.py"}],
            }
        ),
        encoding="utf-8",
    )
    tasks = load_tasks(tmp_path)
    assert tasks[0].id == "repo_nav_1"


def test_validation(tmp_path):
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")
    task = BenchmarkTask(
        id="v1",
        category="feature_implementation",
        description="health",
        workspace=str(tmp_path),
        expected_behavior="health endpoint",
        validation=[
            {"type": "file_contains", "path": "app.py", "text": "FastAPI"},
            {"type": "command", "command": 'python -c "import sys; sys.exit(0)"'},
        ],
    )
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/bench.db")  # type: ignore[call-arg]
    errors = BenchmarkRunner(settings).validate(task, tmp_path)
    assert errors == []
