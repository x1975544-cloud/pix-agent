"""Sandboxed shell execution tool."""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from typing import Any

from pix.errors import ToolError, ToolTimeoutError
from pix.security import ShellPolicy, Workspace, redact_text
from pix.tools.base import Tool


class RunShellTool(Tool):
    """Run a single non-shell command in the workspace.

    The tool intentionally avoids ``shell=True`` and command chaining. Pipelines,
    redirects and destructive commands are rejected by :class:`ShellPolicy`.
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
        command = self.policy.validate(command)
        tokens = shlex.split(command, posix=os.name != "nt")
        if not tokens:
            raise ToolError("Empty shell command")

        env = os.environ.copy()
        # Avoid leaking active credentials through child process listings.
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
            env.pop(key, None)

        started = time.perf_counter()
        try:
            completed = subprocess.run(
                tokens,
                cwd=self.workspace.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolTimeoutError(
                f"Command timed out after {self.timeout_seconds:g}s: {redact_text(command)}"
            ) from exc
        except OSError as exc:
            raise ToolError(f"Failed to start command: {exc}") from exc
        duration = time.perf_counter() - started
        stdout = redact_text(completed.stdout)
        stderr = redact_text(completed.stderr)
        return {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": stdout[:20_000],
            "stderr": stderr[:20_000],
            "duration_seconds": round(duration, 4),
            "timed_out": False,
        }


def default_shell_tool(workspace: Workspace, timeout_seconds: float) -> Tool:
    return RunShellTool(workspace, timeout_seconds=timeout_seconds)
