from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from pix.errors import SecurityError
from pix.sandbox import Sandbox, SandboxResult, SandboxTimeoutError
from pix.verification.engine import VerificationEngine


def _python_command() -> str:
    for name in ("python", "python3", "py"):
        if shutil.which(name):
            return name
    pytest.skip("python executable is required")
    raise AssertionError("unreachable")


class RecordingSandbox(Sandbox):
    def __init__(self, result: SandboxResult) -> None:
        self.result = result
        self.calls: list[tuple[str, Path, float]] = []

    def run(
        self,
        command: str | list[str] | tuple[str, ...],
        *,
        workspace: str | Path,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        self.calls.append((str(command), workspace, timeout))
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
        raise SandboxTimeoutError("timed out")


def test_detect_project_commands(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    engine = VerificationEngine()
    assert engine.detect_test_command(tmp_path) == "python -m pytest -q"


def test_run_tests_ok(tmp_path):
    (tmp_path / "exit_zero.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    engine = VerificationEngine()
    result = engine.run_tests(tmp_path, f"{_python_command()} exit_zero.py", timeout=10)
    assert result.success
    assert result.exit_code == 0


def test_run_tests_failure(tmp_path):
    (tmp_path / "exit_one.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    engine = VerificationEngine()
    result = engine.run_tests(tmp_path, f"{_python_command()} exit_one.py", timeout=10)
    assert not result.success
    assert result.exit_code == 1


def test_run_tests_does_not_bypass_shell_policy(tmp_path):
    engine = VerificationEngine()
    command = "cmd /c exit 0" if os.name == "nt" else "sh -c 'exit 0'"
    with pytest.raises(SecurityError):
        engine.run_tests(tmp_path, command, timeout=10)


def test_run_tests_uses_configured_sandbox(tmp_path):
    sandbox = RecordingSandbox(SandboxResult(return_code=0, stdout="sandbox passed\n"))
    engine = VerificationEngine(sandbox=sandbox)

    result = engine.run_tests(tmp_path, "python check.py", timeout=12)

    assert result.success
    assert result.stdout == "sandbox passed\n"
    assert sandbox.calls == [("python check.py", tmp_path, 12)]


def test_run_tests_captures_sandbox_failure(tmp_path):
    sandbox = RecordingSandbox(SandboxResult(return_code=7, stdout="build output", stderr="test failed"))
    engine = VerificationEngine(sandbox=sandbox)

    result = engine.run_tests(tmp_path, "python check.py")

    assert not result.success
    assert result.exit_code == 7
    assert result.stdout == "build output"
    assert result.stderr == "test failed"


def test_verify_passes_detected_command_to_sandbox(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    sandbox = RecordingSandbox(SandboxResult(return_code=0, stdout="ok\n"))
    engine = VerificationEngine(sandbox=sandbox)

    result = engine.verify(tmp_path, timeout=20)

    assert result.success
    assert sandbox.calls == [("python -m pytest -q", tmp_path, 20)]


def test_run_tests_maps_sandbox_timeout_to_failure_result(tmp_path):
    engine = VerificationEngine(sandbox=TimeoutSandbox())

    result = engine.run_tests(tmp_path, "python check.py", timeout=2)

    assert not result.success
    assert result.exit_code is None
    assert result.stderr == "Command timed out after 2s"


def test_parse_pytest_output():
    parsed = VerificationEngine.parse_result("==== 8 passed, 2 failed, 1 error in 1.2s ====")
    assert parsed["passed"] == 8
    assert parsed["failed"] == 2
    assert parsed["errors"] == 1
