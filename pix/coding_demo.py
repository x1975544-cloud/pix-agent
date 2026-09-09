"""Deterministic autonomous coding dashboard snapshot and demo runner."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pix.config.settings import Settings
from pix.demo import (
    DEMO_PROJECT_DIR,
    DEMO_TASK,
    DemoOutcome,
    prepare_demo_workspace,
    run_autonomous_demo_with_events,
)
from pix.providers.base import ChatMessage, ToolCall
from pix.providers.scripted import ScriptedProvider

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = PROJECT_ROOT / ".demo" / "autonomous-coding-dashboard"
DEFAULT_DATABASE = PROJECT_ROOT / ".demo" / "autonomous-coding-dashboard.db"
DEFAULT_OUTPUT = PROJECT_ROOT / ".demo" / "autonomous-coding-dashboard.json"

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

_EVENT_LABELS = {
    "SESSION_STARTED": "Task received",
    "REPOSITORY_ANALYZED": "Repository analyzed",
    "PLAN_CREATED": "Plan created",
    "REPOSITORY_RETRIEVED": "Repository retrieval",
    "TOOL_CALL": "Tool call",
    "TOOL_RESULT": "Tool result",
    "VERIFICATION_STARTED": "Test run started",
    "VERIFICATION_FINISHED": "Test run finished",
    "GIT_OPERATION": "Git operation",
    "AGENT_FINISHED": "Agent finished",
}

_EVENT_PHASES = {
    "SESSION_STARTED": "task",
    "REPOSITORY_ANALYZED": "repository-retrieval",
    "PLAN_CREATED": "task",
    "REPOSITORY_RETRIEVED": "repository-retrieval",
    "TOOL_CALL": "tool-calls",
    "TOOL_RESULT": "tool-calls",
    "VERIFICATION_STARTED": "test-failure",
    "VERIFICATION_FINISHED": "test-failure",
    "AGENT_FINISHED": "test-success",
}

_SKIPPED_EVENT_TYPES = {
    "ITERATION_STARTED",
    "CONTEXT_BUILD",
    "LLM_REQUEST",
    "LLM_RESPONSE",
    "MEMORY_READ",
    "MEMORY_WRITE",
}


def scripted_demo_messages() -> list[ChatMessage]:
    """Return the exact messages used by the deterministic FizzBuzz demo."""

    plan = {
        "title": "Fix failing FizzBuzz test",
        "summary": "Retrieve the FizzBuzz implementation, reproduce the failure, fix it, and rerun tests.",
        "steps": [
            {"title": "Retrieve", "description": "Search and read the FizzBuzz code."},
            {"title": "Reproduce", "description": "Run the detected test command."},
            {"title": "Fix", "description": "Correct the divisibility order and rerun tests."},
        ],
    }
    return [
        ChatMessage.assistant(json.dumps(plan)),
        ChatMessage.assistant(
            tool_calls=[ToolCall(id="call_search", name="search_code", arguments={"query": "fizzbuzz"})]
        ),
        ChatMessage.assistant(tool_calls=[ToolCall(id="call_read", name="read_file", arguments={"path": "app.py"})]),
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


def scripted_demo_provider() -> ScriptedProvider:
    """Build the provider used by GIF-friendly deterministic dashboard runs."""

    return ScriptedProvider(scripted_demo_messages())


def build_coding_dashboard_snapshot(
    outcome: DemoOutcome,
    events: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Convert one real demo run into a dashboard-friendly snapshot."""

    session_event = _first_event(events, "SESSION_STARTED")
    task = str(session_event.get("payload", {}).get("task") or DEMO_TASK)
    tool_calls = _tool_calls(events)
    verifications = _verifications(events)
    retrieval = _retrieval(outcome, events)
    changed_files = list(outcome.modified_files)
    tool_names = list(outcome.tool_names)

    failed_verification = next((item for item in verifications if not item["success"]), None)
    passed_verification = next((item for item in reversed(verifications) if item["success"]), None)

    if failed_verification:
        test_failure_detail = (
            f"Verification attempt {failed_verification['attempt']} failed; "
            "the output was returned to the agent for autonomous repair."
        )
    elif outcome.verification_failures:
        test_failure_detail = "Automated verification reported failing tests before the repair loop."
    else:
        test_failure_detail = "No test failure was observed."

    repair_tools = [call for call in tool_calls if call["name"] == "write_file"]
    repair_detail = ", ".join(str(call["detail"]) for call in repair_tools) or "No file edits"
    if passed_verification:
        test_success_detail = (
            f"Verification attempt {passed_verification['attempt']} passed "
            f"({outcome.tests_passed} passed, {outcome.tests_failed} failed)."
        )
    else:
        test_success_detail = f"{outcome.tests_passed} tests passed."

    phases = [
        {
            "id": "task",
            "label": "Task",
            "state": "complete",
            "detail": task,
        },
        {
            "id": "repository-retrieval",
            "label": "Repository Retrieval",
            "state": "complete",
            "detail": (f"{retrieval['count']} hit(s) · {', '.join(retrieval['paths'][:3]) or 'repository indexed'}"),
        },
        {
            "id": "tool-calls",
            "label": "Tool Calls",
            "state": "complete",
            "detail": ", ".join(tool_names) if tool_names else "No tools called",
        },
        {
            "id": "test-failure",
            "label": "Test Failure",
            "state": "detected",
            "detail": test_failure_detail,
        },
        {
            "id": "autonomous-repair",
            "label": "Autonomous Repair",
            "state": "complete",
            "detail": repair_detail,
        },
        {
            "id": "test-success",
            "label": "Test Success",
            "state": "success",
            "detail": test_success_detail,
        },
    ]

    return {
        "schema_version": 1,
        "mode": "deterministic-scripted",
        "task": task,
        "phases": phases,
        "tool_calls": tool_calls,
        "retrieval": retrieval,
        "verification": verifications,
        "changed_files": changed_files,
        "timeline": _timeline(events),
        "outcome": outcome.to_dict(),
    }


def run_coding_dashboard(
    *,
    workspace: str | Path | None = None,
    database: str | Path | None = None,
    output: str | Path | None = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    """Run the deterministic demo and persist its dashboard snapshot."""

    destination = Path(workspace or DEFAULT_WORKSPACE).expanduser().resolve()
    if destination == DEMO_PROJECT_DIR.resolve():
        raise ValueError("Coding dashboard workspace must not overwrite the demo source project")
    destination = prepare_demo_workspace(destination)
    outcome, events = run_autonomous_demo_with_events(
        destination,
        provider=scripted_demo_provider(),
        database=database or DEFAULT_DATABASE,
        settings=_dashboard_settings(database or DEFAULT_DATABASE),
    )
    snapshot = build_coding_dashboard_snapshot(outcome, events)
    if output is not None:
        write_coding_dashboard_snapshot(snapshot, output)
    return snapshot


def load_coding_dashboard_snapshot(path: str | Path | None = None) -> dict[str, Any] | None:
    """Read the latest dashboard snapshot without rerunning the demo."""

    target = Path(path or DEFAULT_OUTPUT).expanduser().resolve()
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_coding_dashboard_snapshot(snapshot: dict[str, Any], output: str | Path) -> Path:
    """Write a deterministic snapshot consumed by the web dashboard."""

    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main(argv: Sequence[str] | None = None) -> int:
    """Run and persist one deterministic autonomous coding dashboard demo."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--print-json", action="store_true", help="Print the generated snapshot to stdout.")
    args = parser.parse_args(argv)

    try:
        snapshot = run_coding_dashboard(
            workspace=args.workspace,
            database=args.database,
            output=args.output,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"Coding dashboard demo failed: {exc}", file=sys.stderr)
        return 1

    if args.print_json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote deterministic coding dashboard snapshot to {Path(args.output).resolve()}")
        print(f"Trace: {snapshot['outcome']['trace_id']}")
        print(f"Tests: {snapshot['outcome']['tests_passed']} passed, {snapshot['outcome']['tests_failed']} failed")
    return 0 if snapshot.get("outcome", {}).get("status") == "success" else 1


def _retrieval(outcome: DemoOutcome, events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    event = _first_event(events, "REPOSITORY_RETRIEVED")
    payload = event.get("payload", {}) if event else {}
    paths = [str(path) for path in payload.get("paths") or []]
    if not paths:
        paths = list(outcome.repository_paths)
    return {
        "count": int(payload.get("count") or outcome.repository_retrieval_count),
        "query": str(payload.get("query") or DEMO_TASK),
        "paths": sorted(paths),
    }


def _dashboard_settings(database: str | Path) -> Settings:
    """Build offline settings so deterministic runs never touch a model API."""

    database_path = Path(database).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{database_path.as_posix()}",
        api_key=None,
        api_token=None,
        enable_repository_index=True,
        embedding_provider="local",
        vector_store="memory",
        repository_top_k=5,
        max_iterations=30,
        log_level="ERROR",
    )


def _tool_calls(events: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for event in events:
        event_type = event.get("type")
        payload = event.get("payload", {})
        if event_type == "TOOL_CALL":
            name = str(payload.get("name") or "")
            arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
            calls.append(
                {
                    "name": name,
                    "detail": _arguments_detail(name, arguments),
                    "success": None,
                }
            )
        elif event_type == "TOOL_RESULT" and calls and calls[-1]["success"] is None:
            calls[-1]["success"] = bool(payload.get("success"))
    return calls


def _verifications(events: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload", {})
        if event.get("type") == "VERIFICATION_STARTED":
            pending.append(
                {
                    "attempt": int(payload.get("attempt") or len(attempts) + 1),
                    "command": str(payload.get("command") or ""),
                }
            )
        elif event.get("type") == "VERIFICATION_FINISHED" and pending:
            item = pending.pop(0)
            attempts.append(
                {
                    "attempt": item["attempt"],
                    "command": item["command"],
                    "success": bool(payload.get("success")),
                }
            )
    return attempts


def _timeline(events: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("type") or "")
        if event_type in _SKIPPED_EVENT_TYPES:
            continue
        payload = event.get("payload", {})
        if event_type == "AGENT_FINISHED" and "status" not in payload:
            # AgentLoop emits an intermediate finish before executor verification.
            continue
        phase = _EVENT_PHASES.get(event_type, "task")
        if event_type == "VERIFICATION_STARTED":
            phase = "test-success" if int(payload.get("attempt") or 1) > 1 else "test-failure"
        elif event_type == "VERIFICATION_FINISHED":
            phase = "test-success" if payload.get("success") else "test-failure"
        elif event_type in {"TOOL_CALL", "TOOL_RESULT"} and payload.get("name") == "write_file":
            phase = "autonomous-repair"
        elif event_type == "TOOL_RESULT" and not payload.get("success"):
            phase = "test-failure"
        rows.append(
            {
                "seq": len(rows) + 1,
                "type": event_type,
                "label": _EVENT_LABELS.get(event_type, event_type.replace("_", " ").title()),
                "phase": phase,
                "state": _timeline_state(event_type, payload),
                "detail": _timeline_detail(event_type, payload),
            }
        )
    return rows


def _timeline_state(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "VERIFICATION_FINISHED":
        return "success" if payload.get("success") else "failed"
    if event_type == "TOOL_RESULT":
        return "success" if payload.get("success") else "failed"
    if event_type == "AGENT_FINISHED":
        return "success" if payload.get("status") == "success" else "failed"
    return "complete"


def _timeline_detail(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "REPOSITORY_ANALYZED":
        language = str(payload.get("language") or "unknown")
        framework = str(payload.get("framework") or "unknown")
        return f"{language} · {framework}"
    if event_type == "PLAN_CREATED":
        steps = payload.get("steps")
        count = len(steps) if isinstance(steps, list) else 0
        return f"{str(payload.get('title') or 'Plan')} · {count} steps"
    if event_type == "REPOSITORY_RETRIEVED":
        paths = payload.get("paths") or []
        count = int(payload.get("count") or len(paths))
        return f"{count} hit(s) · {', '.join(str(path) for path in paths[:2])}"
    if event_type == "TOOL_CALL":
        name = str(payload.get("name") or "")
        arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
        return f"{name} · {_arguments_detail(name, arguments)}"
    if event_type == "TOOL_RESULT":
        return "success" if payload.get("success") else "failure"
    if event_type == "VERIFICATION_STARTED":
        return str(payload.get("command") or "detected test command")
    if event_type == "VERIFICATION_FINISHED":
        return "passed" if payload.get("success") else "failed"
    if event_type == "AGENT_FINISHED":
        status = str(payload.get("status") or "finished")
        iterations = payload.get("iterations")
        return f"{status}" if iterations is None else f"{status} · {iterations} iterations"
    if event_type == "SESSION_STARTED":
        return Path(str(payload.get("workspace") or "")).name or "workspace"
    if event_type == "GIT_OPERATION":
        return str(payload.get("action") or payload.get("message") or "")
    return ""


def _arguments_detail(name: str, arguments: dict[str, Any]) -> str:
    if name == "run_shell":
        return str(arguments.get("command") or "run shell")
    if name == "search_code":
        return str(arguments.get("query") or "search repository")
    if name in {"read_file", "write_file"}:
        path = str(arguments.get("path") or "")
        return path if name == "read_file" else f"write {path}"
    for key in ("path", "query", "pattern", "command", "branch"):
        if key in arguments:
            return f"{key}={arguments[key]}"
    return name


def _first_event(events: Sequence[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    return next((event for event in events if event.get("type") == event_type), None)


if __name__ == "__main__":
    raise SystemExit(main())
