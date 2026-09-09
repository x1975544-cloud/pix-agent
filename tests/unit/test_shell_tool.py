from __future__ import annotations

import os

from pix.security import Workspace
from pix.tools.shell import RunShellTool


def test_shell_captures_stdout(tmp_path):
    workspace = Workspace(tmp_path)
    tool = RunShellTool(workspace, timeout_seconds=5)
    command = "cmd /c echo hello pix" if os.name == "nt" else "echo hello pix"
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
    tool = RunShellTool(Workspace(tmp_path), timeout_seconds=5)
    command = "cmd /c exit 3" if os.name == "nt" else "sh -c 'exit 3'"
    result = tool.execute({"command": command})
    assert result.success
    assert result.output["exit_code"] == 3
