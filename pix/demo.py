"""Repeatable single-agent autonomous coding demo."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pix.agent.agent import Agent
from pix.config.settings import Settings
from pix.errors import PiXError
from pix.providers.base import LLMProvider
from pix.verification.engine import VerificationEngine

DEMO_PROJECT_DIR = Path(__file__).resolve().parent.parent / "examples" / "demo-project"
DEMO_TASK = (
    "The demo FastAPI repository has a deliberate FizzBuzz bug that makes its tests fail. "
    "Use repository retrieval, inspect the relevant code, reproduce the failure with the detected "
    "test command, fix the root cause, and rerun the tests until they pass."
)


@dataclass(slots=True)
class DemoOutcome:
    """Final human- and machine-readable report for one demo run."""

    status: str
    trace_id: str
    final_answer: str
    modified_files: list[str] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    repository_retrieval_count: int = 0
    repository_paths: list[str] = field(default_factory=list)
    verification_attempts: int = 0
    verification_failures: int = 0
    test_command: str | None = None
    tests_passed: int = 0
    tests_failed: int = 0
    test_errors: int = 0
    verification_success: bool = False
    verification_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def prepare_demo_workspace(target: str | Path, *, source: str | Path | None = None) -> Path:
    """Copy the demo project into a fresh disposable Git workspace."""

    source_dir = Path(source or DEMO_PROJECT_DIR).expanduser().resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Demo source project not found: {source_dir}")
    destination = Path(target).expanduser().resolve()
    if destination == source_dir:
        raise ValueError("Demo workspace must not overwrite the source project")
    if destination.exists():
        if not destination.is_dir():
            raise ValueError(f"Demo workspace path exists and is not a directory: {destination}")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    shutil.copytree(source_dir, destination, dirs_exist_ok=True)
    _git(destination, "init", "-q")
    _git(destination, "config", "user.email", "pix-demo@example.com")
    _git(destination, "config", "user.name", "PiX Demo")
    _git(destination, "add", ".")
    _git(destination, "commit", "-q", "-m", "chore: initialize demo project")
    return destination


def run_autonomous_demo(
    workspace: str | Path,
    *,
    task: str = DEMO_TASK,
    provider: LLMProvider | None = None,
    settings: Settings | None = None,
    database: str | Path | None = None,
    auto_fix_attempts: int = 2,
) -> DemoOutcome:
    """Run the demo against the existing single-agent runtime."""

    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.is_dir():
        raise FileNotFoundError(f"Demo workspace not found: {workspace_path}")
    active_settings = settings or _demo_settings(database or Path(".demo/autonomous-coding.db"))
    agent = Agent(active_settings, provider=provider)
    try:
        result = agent.run(
            task,
            workspace=workspace_path,
            auto_verify=True,
            auto_fix_attempts=auto_fix_attempts,
        )
        trace_id = result.trace_id or result.state.session_id
        events = agent.trace(trace_id)
    finally:
        agent.close()

    verification = VerificationEngine().verify(workspace_path)
    parsed = VerificationEngine.parse_result(
        f"{verification.stdout}\n{verification.stderr}" if not verification.skipped else ""
    )
    outcome = DemoOutcome(
        status=result.status.value,
        trace_id=trace_id,
        final_answer=result.message,
        modified_files=_modified_files(events, workspace_path),
        tool_names=_tool_names(events),
        repository_retrieval_count=_retrieval_count(events),
        repository_paths=_retrieval_paths(events),
        verification_attempts=_event_count(events, "VERIFICATION_STARTED"),
        verification_failures=_failed_verifications(events),
        test_command=verification.command,
        tests_passed=int(parsed.get("passed") or 0),
        tests_failed=int(parsed.get("failed") or 0),
        test_errors=int(parsed.get("errors") or 0),
        verification_success=verification.success,
        verification_summary=result.state.summary or verification.summary(),
    )
    return outcome


def format_outcome(outcome: DemoOutcome, *, json_output: bool = False) -> str:
    """Render a demo report as JSON or compact terminal text."""

    if json_output:
        return json.dumps(outcome.to_dict(), ensure_ascii=False, indent=2)
    lines = [
        f"Trace ID: {outcome.trace_id}",
        f"Status: {outcome.status}",
        f"Retrieval hits: {outcome.repository_retrieval_count}",
        f"Verification attempts: {outcome.verification_attempts}",
        "Modified files:",
        *[f"- {path}" for path in outcome.modified_files],
        f"Test command: {outcome.test_command or 'none'}",
        (f"Test result: {outcome.tests_passed} passed, {outcome.tests_failed} failed, {outcome.test_errors} errors"),
        f"Verification: {outcome.verification_summary}",
        f"Final answer: {outcome.final_answer}",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for the autonomous coding demo."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(".demo/autonomous-coding"),
        help="Disposable workspace directory.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(".demo/autonomous-coding.db"),
        help="SQLite database used to persist the session and trace.",
    )
    parser.add_argument(
        "--task",
        default=DEMO_TASK,
        help="Natural-language task used for the demo run.",
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Recreate and initialize the workspace before running.",
    )
    parser.add_argument("--json", action="store_true", help="Print a JSON report.")
    args = parser.parse_args(argv)

    try:
        workspace = prepare_demo_workspace(args.workspace) if args.prepare else Path(args.workspace).resolve()
        outcome = run_autonomous_demo(
            workspace,
            task=args.task,
            database=args.database,
        )
    except PiXError as exc:
        print(f"Autonomous coding demo failed: {exc}", file=sys.stderr)
        return 1

    print(format_outcome(outcome, json_output=args.json))
    return 0 if outcome.status == "success" and outcome.verification_success else 1


def _demo_settings(database: str | Path) -> Settings:
    database_path = Path(database).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    env_file = Path.cwd() / ".env"
    return Settings(
        _env_file=str(env_file) if env_file.is_file() else None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{database_path.as_posix()}",
        enable_repository_index=True,
        embedding_provider="local",
        vector_store="memory",
        repository_top_k=5,
        max_iterations=30,
        log_level="ERROR",
    )


def _git(workspace: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )


def _modified_files(events: list[dict[str, Any]], workspace: Path) -> list[str]:
    paths = {
        str(event.get("payload", {}).get("arguments", {}).get("path"))
        for event in events
        if event.get("type") == "TOOL_CALL" and event.get("payload", {}).get("name") == "write_file"
    }
    paths.update(_git_diff_names(workspace))
    return sorted(path for path in paths if path)


def _git_diff_names(workspace: Path) -> set[str]:
    try:
        completed = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if completed.returncode != 0:
        return set()
    return {line for line in completed.stdout.splitlines() if line.strip()}


def _tool_names(events: list[dict[str, Any]]) -> list[str]:
    names = {
        str(event.get("payload", {}).get("name"))
        for event in events
        if event.get("type") == "TOOL_CALL" and event.get("payload", {}).get("name")
    }
    return sorted(names)


def _retrieval_count(events: list[dict[str, Any]]) -> int:
    return sum(int(event.get("payload", {}).get("count") or 0) for event in events if _is_retrieval(event))


def _retrieval_paths(events: list[dict[str, Any]]) -> list[str]:
    paths = {
        str(path) for event in events if _is_retrieval(event) for path in event.get("payload", {}).get("paths") or []
    }
    return sorted(paths)


def _failed_verifications(events: list[dict[str, Any]]) -> int:
    return sum(
        1
        for event in events
        if event.get("type") == "VERIFICATION_FINISHED" and not event.get("payload", {}).get("success")
    )


def _event_count(events: list[dict[str, Any]], event_type: str) -> int:
    return sum(1 for event in events if event.get("type") == event_type)


def _is_retrieval(event: dict[str, Any]) -> bool:
    return event.get("type") == "REPOSITORY_RETRIEVED"


if __name__ == "__main__":
    raise SystemExit(main())
