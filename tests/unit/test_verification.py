from __future__ import annotations

import os

from pix.verification.engine import VerificationEngine


def test_detect_project_commands(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    engine = VerificationEngine()
    assert engine.detect_test_command(tmp_path) == "python -m pytest -q"


def test_run_tests_ok(tmp_path):
    engine = VerificationEngine()
    result = engine.run_tests(tmp_path, 'python -c "import sys; sys.exit(0)"', timeout=10)
    assert result.success
    assert result.exit_code == 0


def test_run_tests_failure(tmp_path):
    engine = VerificationEngine()
    command = "cmd /c exit 1" if os.name == "nt" else "sh -c 'exit 1'"
    result = engine.run_tests(tmp_path, command, timeout=10)
    assert not result.success


def test_parse_pytest_output():
    parsed = VerificationEngine.parse_result("==== 8 passed, 2 failed, 1 error in 1.2s ====")
    assert parsed["passed"] == 8
    assert parsed["failed"] == 2
    assert parsed["errors"] == 1
