"""Shared workspace-bounded process execution for shell and verification."""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Any

from pix.errors import ToolError
from pix.security import ShellPolicy, Workspace


def run_workspace_process(
    command: str,
    *,
    workspace: Workspace,
    timeout: float,
    policy: ShellPolicy | None = None,
) -> tuple[str, str, int]:
    """Validate and run one non-shell process inside a workspace."""

    active_policy = policy or ShellPolicy()
    validated = active_policy.validate(command)
    tokens = shlex.split(validated, posix=os.name != "nt")
    if not tokens:
        raise ToolError("Empty shell command")
    workspace.reject_external_paths(tokens[1:])
    return _run_process(
        tokens,
        cwd=workspace.root,
        env=_child_environment(),
        timeout=timeout,
    )


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
    """Kill the process and its descendants so no child outlives the caller."""

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
