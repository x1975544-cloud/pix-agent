from __future__ import annotations

import json
from pathlib import Path

import pytest
from pix.coding_demo import build_coding_dashboard_snapshot, scripted_demo_provider
from pix.config.settings import Settings
from pix.demo import (
    DEMO_PROJECT_DIR,
    DEMO_TASK,
    format_outcome,
    prepare_demo_workspace,
    run_autonomous_demo_with_events,
)


@pytest.mark.integration
def test_demo_project_contains_intentional_bug() -> None:
    content = (DEMO_PROJECT_DIR / "app.py").read_text(encoding="utf-8")
    assert content.index("if number % 15 == 0:") > content.index("if number % 3 == 0:")


@pytest.mark.integration
def test_autonomous_coding_demo_is_repeatable(tmp_path: Path) -> None:
    for attempt in range(2):
        workspace = prepare_demo_workspace(tmp_path / f"demo-{attempt}")
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url=f"sqlite:///{tmp_path / f'demo-{attempt}.db'}",
            workspace=str(workspace),
            skills_dir=str(tmp_path / f"skills-{attempt}"),
            enable_repository_index=True,
            embedding_provider="local",
            vector_store="memory",
            repository_top_k=5,
            max_iterations=20,
            log_level="ERROR",
        )

        outcome, events = run_autonomous_demo_with_events(
            workspace,
            task=DEMO_TASK,
            provider=scripted_demo_provider(),
            settings=settings,
        )

        assert outcome.status == "success"
        assert outcome.trace_id.startswith("sess_")
        assert outcome.repository_retrieval_count > 0
        assert "app.py" in outcome.repository_paths
        assert {"read_file", "run_shell", "search_code", "write_file"} <= set(outcome.tool_names)
        assert outcome.modified_files == ["app.py"]
        assert outcome.verification_attempts >= 2
        assert outcome.verification_failures == 1
        assert outcome.tests_passed >= 3
        assert outcome.tests_failed == 0
        assert outcome.test_errors == 0
        assert outcome.verification_success is True

        report = json.loads(format_outcome(outcome, json_output=True))
        assert report["trace_id"] == outcome.trace_id
        assert report["modified_files"] == ["app.py"]
        assert report["tests_passed"] >= 3
        assert report["tests_failed"] == 0

        dashboard = build_coding_dashboard_snapshot(outcome, events)
        assert dashboard["mode"] == "deterministic-scripted"
        assert [phase["id"] for phase in dashboard["phases"]] == [
            "task",
            "repository-retrieval",
            "tool-calls",
            "test-failure",
            "autonomous-repair",
            "test-success",
        ]
        assert dashboard["changed_files"] == ["app.py"]
        assert dashboard["verification"][0]["success"] is False
        assert dashboard["verification"][-1]["success"] is True
        assert dashboard["retrieval"]["count"] > 0
        assert "app.py" in dashboard["retrieval"]["paths"]
        assert any(call["name"] == "write_file" for call in dashboard["tool_calls"])
        assert dashboard["timeline"]

        content = (workspace / "app.py").read_text(encoding="utf-8")
        assert content.index("if number % 15 == 0:") < content.index("if number % 3 == 0:")
