"""Git tools with a no-reset safety policy."""

from __future__ import annotations

import subprocess
import time
from typing import Any

from pix.errors import ToolError, ToolTimeoutError
from pix.tools.base import Tool


def _run_git(args: list[str], cwd: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolTimeoutError(f"Git command timed out: {' '.join(args)}") from exc
    duration = time.perf_counter() - started
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ToolError(f"git {' '.join(args)} failed: {detail[:2000]}")
    return {
        "exit_code": 0,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "duration_seconds": round(duration, 4),
    }


class GitStatusTool(Tool):
    name = "git_status"
    description = "Show the current branch and working tree status for the workspace repository."
    parameters = {"type": "object", "properties": {}, "additionalProperties": False}

    def __init__(self, workspace_root: str, timeout_seconds: float = 20.0) -> None:
        self.cwd = workspace_root
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: dict[str, Any]) -> Any:
        result = _run_git(["status", "--short", "--branch"], self.cwd, self.timeout_seconds)
        return {"repository": str(self.cwd), "status": result["stdout"]}


class GitDiffTool(Tool):
    name = "git_diff"
    description = "Show uncommitted changes as a diff against HEAD, including a summary."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional path filter relative to repository root.",
            }
        },
        "additionalProperties": False,
    }

    def __init__(self, workspace_root: str, timeout_seconds: float = 20.0) -> None:
        self.cwd = workspace_root
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: dict[str, Any]) -> Any:
        path_filter = str(arguments["path"]) if arguments.get("path") else None
        if self._has_head():
            args = ["diff", "HEAD", "--no-color"]
            if path_filter:
                args.extend(["--", path_filter])
            result = _run_git(args, self.cwd, self.timeout_seconds)
            stat_args = ["diff", "HEAD", "--stat", "--no-color"]
            if path_filter:
                stat_args.extend(["--", path_filter])
            stat = _run_git(stat_args, self.cwd, self.timeout_seconds)
            return {
                "stat": stat["stdout"],
                "diff": result["stdout"][:30_000],
            }
        status = _run_git(["status", "--short"], self.cwd, self.timeout_seconds)
        unstaged = _run_git(["diff", "--no-color"], self.cwd, self.timeout_seconds)
        return {
            "head": "none",
            "stat": status["stdout"],
            "diff": unstaged["stdout"][:30_000],
            "untracked": status["stdout"],
        }

    def _has_head(self) -> bool:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=self.cwd,
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return completed.returncode == 0


class GitLogTool(Tool):
    name = "git_log"
    description = "Show recent commit history."
    parameters = {
        "type": "object",
        "properties": {"limit": {"type": "integer", "description": "Maximum commits to show.", "default": 20}},
        "additionalProperties": False,
    }

    def __init__(self, workspace_root: str, timeout_seconds: float = 20.0) -> None:
        self.cwd = workspace_root
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: dict[str, Any]) -> Any:
        limit = int(arguments.get("limit", 20))
        result = _run_git(["log", "--oneline", "-n", str(limit)], self.cwd, self.timeout_seconds)
        return {"log": result["stdout"]}


class GitBranchTool(Tool):
    name = "git_branch"
    description = "Show the current branch and available branches."
    parameters = {"type": "object", "properties": {}, "additionalProperties": False}

    def __init__(self, workspace_root: str, timeout_seconds: float = 20.0) -> None:
        self.cwd = workspace_root
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: dict[str, Any]) -> Any:
        current = _run_git(["branch", "--show-current"], self.cwd, self.timeout_seconds)
        branches = _run_git(["branch", "--format=%(refname:short)"], self.cwd, self.timeout_seconds)
        return {"current": current["stdout"], "branches": branches["stdout"].splitlines()}


class GitCommitTool(Tool):
    name = "git_commit"
    description = "Stage all workspace changes and create a commit with the provided message."
    parameters = {
        "type": "object",
        "properties": {"message": {"type": "string", "description": "Concise conventional commit message."}},
        "required": ["message"],
        "additionalProperties": False,
    }

    def __init__(self, workspace_root: str, timeout_seconds: float = 30.0) -> None:
        self.cwd = workspace_root
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: dict[str, Any]) -> Any:
        message = str(arguments["message"]).strip()
        if not message:
            raise ToolError("git_commit requires a non-empty message")
        _run_git(["add", "-A"], self.cwd, self.timeout_seconds)
        status = _run_git(["status", "--short"], self.cwd, self.timeout_seconds)
        if not status["stdout"]:
            return {"committed": False, "reason": "no changes to commit", "message": message}
        commit = _run_git(["commit", "-m", message], self.cwd, self.timeout_seconds)
        short_hash = commit["stdout"].splitlines()[0] if commit["stdout"] else ""
        return {
            "committed": True,
            "message": message,
            "summary": short_hash,
            "files": status["stdout"].splitlines(),
        }


def default_git_tools(workspace_root: str, timeout_seconds: float = 30.0) -> list[Tool]:
    return [
        GitStatusTool(workspace_root, timeout_seconds),
        GitDiffTool(workspace_root, timeout_seconds),
        GitLogTool(workspace_root, timeout_seconds),
        GitBranchTool(workspace_root, timeout_seconds),
        GitCommitTool(workspace_root, timeout_seconds),
    ]
