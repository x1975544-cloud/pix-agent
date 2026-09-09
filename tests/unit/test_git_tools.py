from __future__ import annotations

import subprocess

from pix.tools.git import (
    GitBranchTool,
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitStatusTool,
)


def _init_repo(path):
    for command in (
        ["git", "init"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(command, cwd=path, check=True, capture_output=True)


def test_git_status_diff_and_commit(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('one')\n", encoding="utf-8")
    assert "?? app.py" in GitStatusTool(str(tmp_path)).execute({}).output["status"]

    diff = GitDiffTool(str(tmp_path)).execute({})
    assert diff.success

    commit = GitCommitTool(str(tmp_path)).execute({"message": "feat: add app"})
    assert commit.success
    assert commit.output["committed"] is True

    status = GitStatusTool(str(tmp_path)).execute({})
    assert "?? app.py" not in status.output["status"]
    log = GitLogTool(str(tmp_path)).execute({"limit": 5})
    assert "feat: add app" in log.output["log"]
    branch = GitBranchTool(str(tmp_path)).execute({})
    assert branch.output["current"] in {"master", "main"}


def test_git_diff_isolates_dash_prefixed_path(tmp_path):
    _init_repo(tmp_path)
    dash_file = tmp_path / "-changes.py"
    dash_file.write_text("print('before')\n", encoding="utf-8", newline="")
    subprocess.run(["git", "add", "--", "-changes.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)
    dash_file.write_text("print('after')\n", encoding="utf-8", newline="")

    result = GitDiffTool(str(tmp_path)).execute({"path": "-changes.py"})

    assert result.success
    assert "print('after')" in result.output["diff"]
