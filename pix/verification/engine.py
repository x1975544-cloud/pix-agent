"""Detect and run the appropriate test command for a repository."""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from pix.errors import SandboxError, SandboxTimeoutError, VerificationError
from pix.process import run_workspace_process
from pix.sandbox import Sandbox
from pix.security import ShellPolicy, Workspace, redact_text


@dataclass(slots=True)
class VerificationResult:
    """Result of one verification pass."""

    command: str | None
    success: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    skipped: bool = False

    def summary(self) -> str:
        if self.skipped:
            return f"No test command detected; verification skipped ({self.command or 'none'})."
        tail = (self.stderr.strip().splitlines() or self.stdout.strip().splitlines() or ["no output"])[-1]
        return (
            f"Command: {self.command}\n"
            f"Exit code: {self.exit_code}\n"
            f"Success: {self.success}\n"
            f"Last line: {redact_text(tail[:500])}"
        )


class VerificationEngine:
    """Runs safe project commands and parses their success state."""

    def __init__(
        self,
        *,
        policy: ShellPolicy | None = None,
        sandbox: Sandbox | None = None,
    ) -> None:
        self.policy = policy or ShellPolicy()
        self.sandbox = sandbox

    def detect_project(self, workspace: Path) -> bool:
        return workspace.is_dir()

    def detect_test_command(self, workspace: Path) -> str | None:
        if (workspace / "pyproject.toml").is_file():
            return "uv run pytest -q" if (workspace / "uv.lock").exists() else "python -m pytest -q"
        if (workspace / "package.json").is_file():
            return "npm test -- --runInBand"
        if (workspace / "requirements.txt").is_file() or (workspace / "setup.py").is_file():
            return "python -m pytest -q"
        return None

    def run_tests(self, workspace: Path, command: str, timeout: float = 120.0) -> VerificationResult:
        if not command.strip():
            raise VerificationError("Verification command is empty")
        started = time.perf_counter()
        try:
            if self.sandbox is None:
                stdout, stderr, return_code = run_workspace_process(
                    command,
                    workspace=Workspace(workspace),
                    timeout=timeout,
                    policy=self.policy,
                )
            else:
                sandbox_result = self.sandbox.run(
                    command,
                    workspace=workspace,
                    timeout=timeout,
                )
                stdout = sandbox_result.stdout
                stderr = sandbox_result.stderr
                return_code = sandbox_result.return_code
        except (subprocess.TimeoutExpired, SandboxTimeoutError):
            duration = time.perf_counter() - started
            return VerificationResult(
                command=command,
                success=False,
                stderr=f"Command timed out after {timeout:g}s",
                duration_seconds=duration,
            )
        except OSError as exc:
            raise VerificationError(f"Could not run verification command '{command}': {exc}") from exc
        except SandboxError as exc:
            raise VerificationError(f"Could not run verification command '{command}' in sandbox: {exc}") from exc
        duration = time.perf_counter() - started
        stdout = redact_text(stdout)
        stderr = redact_text(stderr)
        return VerificationResult(
            command=command,
            success=return_code == 0,
            exit_code=return_code,
            stdout=stdout[-30_000:],
            stderr=stderr[-10_000:],
            duration_seconds=duration,
        )

    def verify(self, workspace: Path, timeout: float = 120.0) -> VerificationResult:
        command = self.detect_test_command(workspace)
        if command is None:
            return VerificationResult(command=None, success=True, skipped=True)
        result = self.run_tests(workspace, command, timeout)
        if not result.success:
            result.stderr = self._summarize_pytest_failure(result.stderr or result.stdout)
        return result

    @staticmethod
    def parse_result(output: str) -> dict[str, object]:
        def number(pattern: str) -> int:
            match = re.search(pattern, output, re.MULTILINE)
            return int(match.group(1)) if match else 0

        return {
            "passed": number(r"(?:^|\s)(\d+)\s+passed"),
            "failed": number(r"(?:^|\s)(\d+)\s+failed"),
            "errors": number(r"(?:^|\s)(\d+)\s+errors?\b"),
        }

    @staticmethod
    def _summarize_pytest_failure(output: str) -> str:
        markers = re.findall(r"_{5,}(?: FAILURES| ERROR| _)+|^E .*$", output, re.MULTILINE)
        if markers:
            return output[-4000:]
        return output
