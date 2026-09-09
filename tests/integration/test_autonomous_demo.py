from __future__ import annotations

import json
from pathlib import Path

import pytest
from pix.config.settings import Settings
from pix.demo import (
    DEMO_PROJECT_DIR,
    DEMO_TASK,
    format_outcome,
    prepare_demo_workspace,
    run_autonomous_demo,
)
from pix.providers.base import ChatMessage, ToolCall
from tests.conftest import ScriptedProvider

CORRECT_APP = """from fastapi import FastAPI

app = FastAPI(title="Demo FastAPI")


def fizzbuzz(number: int) -> str:
    if number % 15 == 0:
        return "FizzBuzz"
    if number % 3 == 0:
        return "Fizz"
    if number % 5 == 0:
        return "Buzz"
    return str(number)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/fizzbuzz/{number}")
def fizzbuzz_endpoint(number: int) -> dict[str, str]:
    return {"value": fizzbuzz(number)}
"""


def _demo_provider() -> ScriptedProvider:
    plan = {
        "title": "Fix failing FizzBuzz test",
        "summary": "Retrieve the FizzBuzz implementation, reproduce the failure, fix it, and rerun tests.",
        "steps": [
            {"title": "Retrieve", "description": "Search and read the FizzBuzz code."},
            {"title": "Reproduce", "description": "Run the detected test command."},
            {"title": "Fix", "description": "Correct the divisibility order and rerun tests."},
        ],
    }
    return ScriptedProvider(
        [
            ChatMessage.assistant(json.dumps(plan)),
            ChatMessage.assistant(
                tool_calls=[ToolCall(id="call_search", name="search_code", arguments={"query": "fizzbuzz"})]
            ),
            ChatMessage.assistant(
                tool_calls=[ToolCall(id="call_read", name="read_file", arguments={"path": "app.py"})]
            ),
            ChatMessage.assistant(
                tool_calls=[
                    ToolCall(
                        id="call_tests",
                        name="run_shell",
                        arguments={"command": "uv run pytest -q"},
                    )
                ]
            ),
            ChatMessage.assistant("I reproduced the failing FizzBuzz tests."),
            ChatMessage.assistant(
                tool_calls=[
                    ToolCall(
                        id="call_write",
                        name="write_file",
                        arguments={"path": "app.py", "content": CORRECT_APP},
                    )
                ]
            ),
            ChatMessage.assistant("I fixed the divisibility order and the tests pass."),
        ]
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

        outcome = run_autonomous_demo(
            workspace,
            task=DEMO_TASK,
            provider=_demo_provider(),
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

        content = (workspace / "app.py").read_text(encoding="utf-8")
        assert content.index("if number % 15 == 0:") < content.index("if number % 3 == 0:")
