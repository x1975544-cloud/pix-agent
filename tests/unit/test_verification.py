from __future__ import annotations

import os
import shutil

import pytest
from pix.errors import SecurityError
from pix.verification.engine import VerificationEngine


def _python_command() -> str:
    for name in ("python", "python3", "py"):
        if shutil.which(name):
            return name
    pytest.skip("python executable is required")
    raise AssertionError("unreachable")


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


def test_parse_pytest_output():
    parsed = VerificationEngine.parse_result("==== 8 passed, 2 failed, 1 error in 1.2s ====")
    assert parsed["passed"] == 8
    assert parsed["failed"] == 2
    assert parsed["errors"] == 1
