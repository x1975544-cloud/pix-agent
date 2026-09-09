from __future__ import annotations

import shutil
import time

import pytest
from pix.security import Workspace
from pix.tools.shell import RunShellTool


def _python_command() -> str:
    for name in ("python", "python3", "py"):
        if shutil.which(name):
            return name
    pytest.skip("python executable is required")
    raise AssertionError("unreachable")


def test_shell_captures_stdout(tmp_path):
    (tmp_path / "hello.py").write_text("print('hello pix')\n", encoding="utf-8")
    workspace = Workspace(tmp_path)
    tool = RunShellTool(workspace, timeout_seconds=5)
    command = f"{_python_command()} hello.py"
    result = tool.execute({"command": command})
    assert result.success
    assert result.output["stdout"].strip() == "hello pix"
    assert result.output["exit_code"] == 0


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
