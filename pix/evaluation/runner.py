"""Run benchmark tasks against a live agent and produce honest reports."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pix.agent.agent import Agent
from pix.config.settings import Settings
from pix.evaluation.dataset import BenchmarkTask, ValidationRule, load_tasks
from pix.evaluation.metrics import BenchmarkMetrics


@dataclass(slots=True)
class TaskRun:
    task: BenchmarkTask
    started_at: str
    finished_at: str
    success: bool
    session_id: str | None = None
    status: str | None = None
    message: str = ""
    latency_seconds: float = 0.0
    validation_errors: list[str] = field(default_factory=list)
    summary: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.task.id,
            "category": self.task.category,
            "description": self.task.description,
            "workspace": self.task.workspace,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "success": self.success,
            "session_id": self.session_id,
            "status": self.status,
            "latency_seconds": round(self.latency_seconds, 3),
            "validation_errors": self.validation_errors,
            "message": self.message[:2000],
            "summary": self.summary[:2000],
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


@dataclass(slots=True)
class BenchmarkReport:
    generated_at: str
    runs: list[TaskRun]
    metrics: BenchmarkMetrics

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "metrics": {
                "total": self.metrics.total,
                "passed": self.metrics.passed,
                "failed": self.metrics.failed,
                "success_rate": round(self.metrics.success_rate, 4),
                "average_latency_seconds": round(self.metrics.average_latency, 4),
                "average_tool_calls": round(self.metrics.average_tool_calls, 4),
                "average_input_tokens": round(self.metrics.average_input_tokens, 4),
                "average_output_tokens": round(self.metrics.average_output_tokens, 4),
            },
            "runs": [run.to_dict() for run in self.runs],
        }

    def summary_markdown(self) -> str:
        metrics = self.metrics
        lines = [
            f"# PiX Benchmark Report - {self.generated_at}",
            "",
            f"- Success rate: {metrics.success_rate:.0%} ({metrics.passed}/{metrics.total})",
            f"- Average latency: {metrics.average_latency:.1f}s",
            f"- Average tool calls: {metrics.average_tool_calls:.1f}",
            f"- Average input tokens: {metrics.average_input_tokens:.0f}",
            f"- Average output tokens: {metrics.average_output_tokens:.0f}",
            "",
            "| Task | Status | Latency | Validation |",
            "| --- | --- | --- | --- |",
        ]
        for run in self.runs:
            errors = "; ".join(run.validation_errors) or "passed"
            lines.append(
                f"| {run.task.id} | {'PASS' if run.success else 'FAIL'} | {run.latency_seconds:.1f}s | {errors} |"
            )
        return "\n".join(lines)


class BenchmarkRunner:
    """Execute tasks with the real agent and validate each result."""

    def __init__(self, settings: Settings, *, agent: Agent | None = None) -> None:
        self.settings = settings
        self._agent = agent

    def run_directory(self, directory: str | Path) -> BenchmarkReport:
        tasks = load_tasks(directory)
        runs: list[TaskRun] = []
        agent = self._agent or Agent(self.settings)
        try:
            for task in tasks:
                runs.append(self.run_task(task, agent))
        finally:
            if self._agent is None:
                agent.close()
        metrics = BenchmarkMetrics(
            total=len(runs),
            passed=sum(1 for run in runs if run.success),
            failed=sum(1 for run in runs if not run.success),
            total_latency=sum(run.latency_seconds for run in runs),
            total_input_tokens=sum(run.input_tokens for run in runs),
            total_output_tokens=sum(run.output_tokens for run in runs),
        )
        report = BenchmarkReport(generated_at=datetime.now(UTC).isoformat(), runs=runs, metrics=metrics)
        self._write_report(report)
        return report

    def run_task(self, task: BenchmarkTask, agent: Agent) -> TaskRun:
        started = time.perf_counter()
        started_at = datetime.now(UTC).isoformat()
        workspace = Path(task.workspace)
        if not workspace.is_absolute():
            workspace = Path.cwd() / workspace
        result = agent.run(task.description, workspace=workspace, auto_verify=False)
        latency = time.perf_counter() - started
        errors = self.validate(task, workspace)
        success = result.status.value == "success" and not errors
        input_tokens, output_tokens = self._token_totals(agent, result.state.session_id)
        return TaskRun(
            task=task,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            success=success,
            session_id=result.state.session_id,
            status=result.status.value,
            message=result.message,
            latency_seconds=latency,
            validation_errors=errors,
            summary=result.state.summary or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def validate(self, task: BenchmarkTask, workspace: Path) -> list[str]:
        errors: list[str] = []
        for rule in task.validation:
            error = self._validate_rule(rule, workspace)
            if error:
                errors.append(error)
        return errors

    @staticmethod
    def _validate_rule(rule: ValidationRule, workspace: Path) -> str | None:
        if rule.type == "file_exists":
            if not rule.path or not (workspace / rule.path).is_file():
                return f"missing file: {rule.path}"
            return None
        if rule.type == "file_contains":
            if not rule.path or not (workspace / rule.path).is_file():
                return f"missing file: {rule.path}"
            if rule.text is None:
                return f"file_contains rule requires text for {rule.path}"
            content = (workspace / rule.path).read_text(encoding="utf-8", errors="replace")
            if rule.text not in content:
                return f"pattern not found in {rule.path}: {rule.text}"
            return None
        if rule.type == "command":
            try:
                completed = subprocess.run(
                    rule.command or "",
                    shell=False,
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=rule.timeout,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return f"command failed to run: {exc}"
            if completed.returncode != 0:
                return f"command failed ({completed.returncode}): {completed.stderr[:400]}"
            return None
        return "unsupported validation rule"

    @staticmethod
    def _token_totals(agent: Agent, session_id: str) -> tuple[int, int]:
        input_tokens = 0
        output_tokens = 0
        for event in agent.trace(session_id):
            if event.get("type") != "LLM_RESPONSE":
                continue
            usage = event.get("payload", {}).get("usage") or {}
            input_tokens += int(usage.get("input_tokens") or 0)
            output_tokens += int(usage.get("output_tokens") or 0)
        return input_tokens, output_tokens

    @staticmethod
    def _write_report(report: BenchmarkReport) -> None:
        output_dir = Path("benchmarks/results")
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        (output_dir / f"report-{stamp}.json").write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / f"report-{stamp}.md").write_text(report.summary_markdown() + "\n", encoding="utf-8")
