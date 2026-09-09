"""Sandboxing, redaction and dangerous-command policies."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pix.errors import SecurityError

_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[^\s'\"]{6,}", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
]

_SENSITIVE_KEYS = {
    "api_key",
    "openai_api_key",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "authorization",
    "cookie",
    "x-api-key",
}


def redact_text(text: str, extra_secrets: Iterable[str] = ()) -> str:
    """Replace known secrets with a fixed placeholder."""

    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    for secret in extra_secrets:
        if secret and secret != "[REDACTED]":
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def redact_payload(payload: Any, extra_secrets: Iterable[str] = ()) -> Any:
    """Recursively redact secret-looking keys and values from trace payloads."""

    if isinstance(payload, dict):
        return {
            key: ("[REDACTED]" if key.lower() in _SENSITIVE_KEYS else redact_payload(value, extra_secrets))
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [redact_payload(item, extra_secrets) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_payload(item, extra_secrets) for item in payload)
    if isinstance(payload, str):
        return redact_text(payload, extra_secrets)
    return payload


class Workspace:
    """Filesystem sandbox that rejects access outside its root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def resolve(self, relative_or_absolute: str | Path) -> Path:
        """Resolve a path and verify that it stays inside the workspace root."""

        candidate = Path(relative_or_absolute).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise SecurityError(f"Path escapes workspace root: {relative_or_absolute}") from exc
        return resolved

    def exists(self, path: str | Path) -> bool:
        return self.resolve(path).exists()

    def is_within(self, path: str | Path) -> bool:
        try:
            self.resolve(path)
            return True
        except SecurityError:
            return False


DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+(-[A-Za-z]*[rRfF][A-Za-z]*\s+)+/+\s*$"),
    re.compile(r"\brm\s+(-[A-Za-z]*[rRfF][A-Za-z]*\s+)+/\s"),
    re.compile(r"\brm\s+(-[A-Za-z]*[rRfF][A-Za-z]*\s+)*(?:[~*]|/[/~*]|\.\.)"),
    re.compile(r"\brm\s+-rf\s+[.~]"),
    re.compile(r"\bmkfs(?:\.\w+)?\b"),
    re.compile(r"\bformat\s+[A-Za-z]:"),
    re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b|\bpoweroff\b"),
    re.compile(r"\bdd\s+.*\bof=/dev/"),
    re.compile(r">\s*/dev/sd"),
    re.compile(r":\(\)\s*\{\s*:|fork\s*bomb"),
    re.compile(r"\bgit\s+reset\s+(--hard|--mixed|--soft)"),
    re.compile(r"\bgit\s+reflog\s+delete"),
    re.compile(r"\bgit\s+filter-branch"),
    re.compile(r"\bgit\s+clean\s+-[A-Za-z]*[fF]"),
    re.compile(r"\bcurl\b.*\|\s*(?:ba)?sh\b"),
    re.compile(r"\s(?:&&|\|\||;)\s"),
    re.compile(r"\s(?:>|>>|<|<<)\s"),
]

FORBIDDEN_COMMANDS = {
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "mkfs",
    "mkfs.ext4",
    "mkfs.xfs",
}


class ShellPolicy:
    """Decide whether a shell command may run inside an agent session."""

    def __init__(self, extra_deny_terms: Iterable[str] = ()) -> None:
        self.extra_deny_terms = frozenset(term.lower() for term in extra_deny_terms)

    def validate(self, command: str) -> str:
        """Return the validated command or raise :class:`SecurityError`."""

        stripped = command.strip()
        if not stripped:
            raise SecurityError("Empty shell command")
        lower = stripped.lower()
        first_word = stripped.split(maxsplit=1)[0].lower() if stripped else ""
        if first_word in FORBIDDEN_COMMANDS or first_word in self.extra_deny_terms:
            raise SecurityError(f"Command is forbidden by shell policy: {first_word}")
        if any(pattern.search(lower) for pattern in DANGEROUS_PATTERNS):
            raise SecurityError("Command matches a dangerous shell pattern")
        return stripped


def is_binary(data: bytes) -> bool:
    """Heuristic binary detection using NUL bytes and control characters."""

    if b"\x00" in data[:8192]:
        return True
    sample = data[:8192]
    control = sum(byte < 9 or 13 < byte < 32 for byte in sample)
    return bool(sample) and control / len(sample) > 0.3
