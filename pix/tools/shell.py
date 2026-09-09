"""Workspace-bounded process execution tool with optional sandbox isolation."""

from __future__ import annotations

import subprocess
import time
from typing import Any

from pix.errors import SandboxError, SandboxTimeoutError, ToolError, ToolTimeoutError
from pix.process import run_workspace_process
from pix.sandbox import Sandbox
from pix.security import ShellPolicy, Workspace, redact_text
from pix.tools.base import Tool


class RunShellTool(Tool):
    """Run a project process, optionally inside a configured sandbox.

    This layer rejects shell wrappers, inline interpreter code and command
    paths outside the workspace. Without a sandbox it is process-level
    hardening: a project command such as pytest or npm test can still execute
    workspace code with the host user's filesystem permissions. When a
    :class:`Sandbox` is supplied, the process runs inside that isolated
    boundary instead.
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
        sandbox: Sandbox | None = None,
    ) -> None:
        self.workspace = workspace
        self.timeout_seconds = timeout_seconds
        self.policy = policy or ShellPolicy()
        self.sandbox = sandbox

    def run(self, arguments: dict[str, Any]) -> Any:
        command = str(arguments["command"])

        started = time.perf_counter()
        try:
            if self.sandbox is None:
                stdout, stderr, return_code = run_workspace_process(
                    command,
                    workspace=self.workspace,
                    timeout=self.timeout_seconds,
                    policy=self.policy,
                )
            else:
                self.policy.validate(command)
                sandbox_result = self.sandbox.run(
                    command,
                    workspace=self.workspace.root,
                    timeout=self.timeout_seconds,
                )
                stdout = sandbox_result.stdout
                stderr = sandbox_result.stderr
                return_code = sandbox_result.return_code
        except (subprocess.TimeoutExpired, SandboxTimeoutError) as exc:
            raise ToolTimeoutError(
                f"Command timed out after {self.timeout_seconds:g}s: {redact_text(command)}"
            ) from exc
        except OSError as exc:
            raise ToolError(f"Failed to start command: {exc}") from exc
        except SandboxError as exc:
            raise ToolError(f"Failed to run command in sandbox: {exc}") from exc
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


def default_shell_tool(
    workspace: Workspace,
    timeout_seconds: float,
    *,
    sandbox: Sandbox | None = None,
) -> Tool:
    return RunShellTool(workspace, timeout_seconds=timeout_seconds, sandbox=sandbox)
