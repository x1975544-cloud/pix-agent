from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from pix.sandbox import Sandbox, SandboxResult, SandboxTimeoutError
from pix.security import Workspace
from pix.tools.shell import RunShellTool, default_shell_tool


def _python_command() -> str:
    for name in ("python", "python3", "py"):
        if shutil.which(name):
            return name
    pytest.skip("python executable is required")
    raise AssertionError("unreachable")


class RecordingSandbox(Sandbox):
    def __init__(self, result: SandboxResult | None = None) -> None:
        self.result = result or SandboxResult(return_code=0, stdout="sandbox output\n")
        self.calls: list[tuple[str, Path, float]] = []

    def run(
        self,
        command: str | list[str] | tuple[str, ...],
        *,
        workspace: str | Path,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        self.calls.append((str(command), Path(workspace), timeout))
        return self.result


class TimeoutSandbox(Sandbox):
    def run(
        self,
        command: str | list[str] | tuple[str, ...],
        *,
        workspace: str | Path,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        raise SandboxTimeoutError("command timed out in sandbox")


def test_shell_captures_stdout(tmp_path):
    (tmp_path / "hello.py").write_text("print('hello pix')\n", encoding="utf-8")
    workspace = Workspace(tmp_path)
    tool = RunShellTool(workspace, timeout_seconds=5)
    command = f"{_python_command()} hello.py"
    result = tool.execute({"command": command})
    assert result.success
    assert result.output["stdout"].strip() == "hello pix"
    assert result.output["exit_code"] == 0


def test_shell_runs_in_configured_sandbox(tmp_path):
    sandbox = RecordingSandbox(SandboxResult(return_code=3, stdout="sandbox stdout", stderr="sandbox stderr"))
    tool = RunShellTool(Workspace(tmp_path), timeout_seconds=7, sandbox=sandbox)

    result = tool.execute({"command": "python check.py"})

    assert result.success
    assert result.output["exit_code"] == 3
    assert result.output["stdout"] == "sandbox stdout"
    assert result.output["stderr"] == "sandbox stderr"
    assert sandbox.calls == [("python check.py", tmp_path.resolve(), 7)]


def test_shell_still_applies_policy_with_sandbox(tmp_path):
    sandbox = RecordingSandbox()
    tool = RunShellTool(Workspace(tmp_path), timeout_seconds=5, sandbox=sandbox)

    result = tool.execute({"command": "rm -rf /"})

    assert not result.success
    assert "dangerous" in (result.error or "").lower()
    assert sandbox.calls == []


def test_shell_maps_sandbox_timeout(tmp_path):
    tool = RunShellTool(Workspace(tmp_path), timeout_seconds=5, sandbox=TimeoutSandbox())

    result = tool.execute({"command": "python slow.py"})

    assert not result.success
    assert "timed out" in (result.error or "").lower()


def test_shell_redacts_and_truncates_sandbox_output(tmp_path):
    secret = f"sk-{'a' * 40}"
    sandbox = RecordingSandbox(SandboxResult(return_code=0, stdout=secret + "\n" + ("x" * 21_000)))
    tool = RunShellTool(Workspace(tmp_path), timeout_seconds=5, sandbox=sandbox)

    result = tool.execute({"command": "python secret.py"})

    assert result.success
    assert len(result.output["stdout"]) == 20_000
    assert secret not in result.output["stdout"]
    assert "[REDACTED]" in result.output["stdout"]


def test_default_shell_tool_accepts_sandbox(tmp_path):
    sandbox = RecordingSandbox(SandboxResult(return_code=0, stdout="helper output\n"))
    tool = default_shell_tool(Workspace(tmp_path), timeout_seconds=4, sandbox=sandbox)

    result = tool.execute({"command": "python helper.py"})

    assert result.success
    assert result.output["stdout"].strip() == "helper output"
    assert sandbox.calls == [("python helper.py", tmp_path.resolve(), 4)]


def test_shell_rejects_dangerous_command(tmp_path):
    tool = RunShellTool(Workspace(tmp_path), timeout_seconds=5)
    result = tool.execute({"command": "rm -rf /"})
    assert not result.success
    assert "dangerous" in (result.error or "").lower()


def test_shell_captures_nonzero_exit(tmp_path):
    (tmp_path / "exit_three.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
    tool = RunShellTool(Workspace(tmp_path), timeout_seconds=5)
    command = f"{_python_command()} exit_three.py"
    result = tool.execute({"command": command})
    assert result.success
    assert result.output["exit_code"] == 3


def test_shell_rejects_external_path_argument(tmp_path):
    outside = tmp_path.parent / "secret.py"
    outside.write_text("print('outside reached')\n", encoding="utf-8")
    tool = RunShellTool(Workspace(tmp_path), timeout_seconds=5)
    result = tool.execute({"command": f"{_python_command()} ../secret.py"})
    assert not result.success
    assert "workspace" in (result.error or "").lower()


def test_shell_rejects_inline_code(tmp_path):
    tool = RunShellTool(Workspace(tmp_path), timeout_seconds=5)
    for command in (
        'python -c "import pathlib; print(pathlib.Path.home())"',
        "node -e \"require('fs').readFileSync('/etc/passwd')\"",
        "sh -c 'cat /etc/passwd'",
        "cmd /c type C:\\outside.txt",
    ):
        result = tool.execute({"command": command})
        assert not result.success
        assert "forbidden" in (result.error or "").lower() or "wrapper" in (result.error or "").lower()


def test_shell_timeout_cleans_up_process_tree(tmp_path):
    workspace = Workspace(tmp_path)
    (tmp_path / "spawn_loop.py").write_text(
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "subprocess.Popen(\n"
        "    [sys.executable, '-c', \"import time\\nwhile True:\\n"
        "        open('marker.txt', 'a').write('x'); time.sleep(0.02)\"],\n"
        "    stdout=subprocess.DEVNULL,\n"
        "    stderr=subprocess.DEVNULL,\n"
        ")\n"
        "while True:\n"
        "    time.sleep(0.02)\n",
        encoding="utf-8",
    )
    tool = RunShellTool(workspace, timeout_seconds=0.4)
    result = tool.execute({"command": f"{_python_command()} spawn_loop.py"})
    assert not result.success
    assert "timed out" in (result.error or "").lower()

    heartbeat = tmp_path / "marker.txt"
    size_before = heartbeat.stat().st_size if heartbeat.exists() else 0
    time.sleep(0.3)
    size_after = heartbeat.stat().st_size if heartbeat.exists() else 0
    assert size_after == size_before
