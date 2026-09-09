"""Workspace-bounded process execution tool with defense-in-depth checks."""

from __future__ import annotations

import subprocess
import time
from typing import Any

from pix.errors import ToolError, ToolTimeoutError
from pix.process import run_workspace_process
from pix.security import ShellPolicy, Workspace, redact_text
from pix.tools.base import Tool


class RunShellTool(Tool):
    """Run a project process with the workspace as its current directory.

    This layer rejects shell wrappers, inline interpreter code and command
    paths outside the workspace. It is process-level hardening, not an OS
    sandbox: a project command such as pytest or npm test can still execute
    workspace code that has the host user's filesystem permissions.
    """

    name = "run_shell"
    description = (
        "Run a process in the workspace and capture stdout, stderr, exit code and duration. "
        "Use this only for project commands such as pytest, npm test or lint; prefer dedicated tools for Git."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Command line to execute, e.g. 'python -m pytest -q'.",
            }
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        workspace: Workspace,
        *,
        timeout_seconds: float = 60.0,
        policy: ShellPolicy | None = None,
    ) -> None:
        self.workspace = workspace
        self.timeout_seconds = timeout_seconds
        self.policy = policy or ShellPolicy()

    def run(self, arguments: dict[str, Any]) -> Any:
        command = str(arguments["command"])

        started = time.perf_counter()
        try:
            stdout, stderr, return_code = run_workspace_process(
                command,
                workspace=self.workspace,
                timeout=self.timeout_seconds,
                policy=self.policy,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolTimeoutError(
                f"Command timed out after {self.timeout_seconds:g}s: {redact_text(command)}"
            ) from exc
        except OSError as exc:
            raise ToolError(f"Failed to start command: {exc}") from exc
        duration = time.perf_counter() - started
        stdout = redact_text(stdout)
        stderr = redact_text(stderr)
        return {
            "command": command,
            "exit_code": return_code,
            "stdout": stdout[:20_000],
            "stderr": stderr[:20_000],
            "duration_seconds": round(duration, 4),
            "timed_out": False,
        }


def default_shell_tool(workspace: Workspace, timeout_seconds: float) -> Tool:
    return RunShellTool(workspace, timeout_seconds=timeout_seconds)
