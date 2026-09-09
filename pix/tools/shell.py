"""Workspace-bounded process execution tool with defense-in-depth checks."""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from pix.errors import ToolError, ToolTimeoutError
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
        command = self.policy.validate(command)
        tokens = shlex.split(command, posix=os.name != "nt")
        if not tokens:
            raise ToolError("Empty shell command")
        self.workspace.reject_external_paths(tokens[1:])

        env = _child_environment()

        started = time.perf_counter()
        try:
            stdout, stderr, return_code = _run_process(
                tokens,
                cwd=self.workspace.root,
                env=env,
                timeout=self.timeout_seconds,
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


_CREDENTIAL_HINTS = (
    "API_KEY",
    "ACCESS_TOKEN",
    "AUTH_TOKEN",
    "CLIENT_SECRET",
    "CREDENTIAL",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "SECRET",
    "TOKEN",
)

_CODE_INJECTION_VARIABLES = {
    "BUN_OPTIONS",
    "DENO_OPTIONS",
    "DOTNET_STARTUP_HOOKS",
    "DYLD_INSERT_LIBRARIES",
    "JAVA_TOOL_OPTIONS",
    "JDK_JAVA_OPTIONS",
    "LD_PRELOAD",
    "NODE_OPTIONS",
    "PERL5OPT",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "RUBYOPT",
}


def _child_environment() -> dict[str, str]:
    """Build an environment without credentials or interpreter startup hooks."""

    env = os.environ.copy()
    for key in tuple(env):
        upper = key.upper()
        if any(hint in upper for hint in _CREDENTIAL_HINTS) or upper in _CODE_INJECTION_VARIABLES:
            env.pop(key, None)
    return env


def _run_process(
    tokens: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
) -> tuple[str, str, int]:
    """Run one process and terminate its whole process tree on timeout."""

    kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if os.name == "posix":
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    with subprocess.Popen(tokens, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(process)
            with suppress(subprocess.TimeoutExpired):
                process.communicate(timeout=2)
            raise
        return_code = process.returncode
        if return_code is None:
            process.wait(timeout=5)
            return_code = process.returncode
        return stdout or "", stderr or "", int(return_code or 0)


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Kill the process and its descendants so no child outlives the tool."""

    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        else:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        return

    try:
        completed = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
    else:
        if completed.returncode != 0:
            process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def default_shell_tool(workspace: Workspace, timeout_seconds: float) -> Tool:
    return RunShellTool(workspace, timeout_seconds=timeout_seconds)
