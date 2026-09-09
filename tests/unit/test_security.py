from __future__ import annotations

import pytest
from pix.errors import SecurityError
from pix.security import ShellPolicy, Workspace, redact_payload, redact_text


def test_workspace_accepts_relative_path(tmp_path):
    workspace = Workspace(tmp_path)
    resolved = workspace.resolve("src/file.py")
    assert resolved == (tmp_path / "src/file.py").resolve()


def test_workspace_rejects_traversal(tmp_path):
    workspace = Workspace(tmp_path)
    with pytest.raises(SecurityError):
        workspace.resolve("../outside.txt")


def test_workspace_rejects_absolute_escape(tmp_path):
    workspace = Workspace(tmp_path)
    with pytest.raises(SecurityError):
        workspace.resolve(tmp_path.parent)


def test_redaction_hides_api_keys():
    text = "key=sk-abcdef1234567890 and token=supersecretvalue123"
    redacted = redact_text(text)
    assert "sk-abcdef1234567890" not in redacted
    assert "supersecretvalue123" not in redacted
    assert "[REDACTED]" in redacted


def test_redaction_hides_known_extra_secret():
    assert redact_text("value is my-private-token", ["my-private-token"]) == "value is [REDACTED]"


def test_redact_payload_handles_nested_sensitive_keys():
    payload = {"message": "ok", "authorization": "Bearer abc123", "nested": {"api_key": "12345678"}}
    result = redact_payload(payload)
    assert result["authorization"] == "[REDACTED]"
    assert result["nested"]["api_key"] == "[REDACTED]"


def test_shell_policy_rejects_destructive_commands():
    policy = ShellPolicy()
    for command in ("rm -rf /", "shutdown now", "git reset --hard HEAD", "echo a && echo b"):
        with pytest.raises(SecurityError):
            policy.validate(command)


def test_shell_policy_accepts_project_commands():
    policy = ShellPolicy()
    assert policy.validate("python -m pytest -q") == "python -m pytest -q"
