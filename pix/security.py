"""Sandboxing, redaction and dangerous-command policies."""

from __future__ import annotations

import os
import re
import shlex
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

    def reject_external_paths(self, arguments: Iterable[str]) -> None:
        """Reject command arguments that point outside the workspace root."""

        for argument in arguments:
            path_text = _command_path_argument(argument)
            if path_text is None:
                continue
            candidate = Path(path_text).expanduser()
            if not candidate.is_absolute():
                candidate = self.root / candidate
            try:
                resolved = candidate.resolve()
                resolved.relative_to(self.root)
            except ValueError as exc:
                raise SecurityError(f"Command path escapes workspace root: {argument}") from exc


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
    re.compile(r"\b(?:rd|rmdir)\s+(?:[/-]s\s*)?[/-]q"),
    re.compile(r"\bRemove-Item\b|\bRemove-ChildItem\b"),
    re.compile(r"\s(?:&&|\|\||;)\s"),
    re.compile(r"\s(?:>|>>|<|<<)\s"),
]

FORBIDDEN_COMMANDS = {
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "del",
    "deltree",
    "erase",
    "rd",
    "rmdir",
    "mkfs",
    "mkfs.ext4",
    "mkfs.xfs",
}

_SHELL_WRAPPERS = {
    "ash",
    "bash",
    "busybox",
    "cmd",
    "command.com",
    "csh",
    "dash",
    "env",
    "fish",
    "ksh",
    "powershell",
    "pwsh",
    "sh",
    "sudo",
    "tcsh",
    "wsl",
    "zsh",
}

_INLINE_EVAL_FLAGS = {
    "bun": {"-e", "--eval"},
    "deno": set(),
    "node": {"-e", "--eval", "-p", "--print"},
    "nodejs": {"-e", "--eval", "-p", "--print"},
    "perl": {"-e"},
    "php": {"-r"},
    "py": {"-c"},
    "python": {"-c"},
    "python3": {"-c"},
    "pythonw": {"-c"},
    "ruby": {"-e"},
}

_STDIN_CODE_COMMANDS = {
    "node",
    "nodejs",
    "perl",
    "php",
    "py",
    "python",
    "python3",
    "pythonw",
    "ruby",
}

_OPTIONS_WITH_VALUES = {
    "node": {"--import", "--loader", "--require", "-r"},
    "nodejs": {"--import", "--loader", "--require", "-r"},
    "py": {"-W", "-X"},
    "python": {"-W", "-X"},
    "python3": {"-W", "-X"},
    "pythonw": {"-W", "-X"},
}

_PATH_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_FILE_URI = re.compile(r"^file://", re.IGNORECASE)
_PYTHON_EXECUTABLE = re.compile(r"^(?:py|python\d*(?:\.\d+)*|pythonw|pypy\d*(?:\.\d+)*)$")


def _command_name(token: str) -> str:
    """Return a normalized executable name from a command token."""

    name = _strip_outer_quotes(token.strip()).lower()
    name = re.split(r"[\\/]", name)[-1]
    return name.removesuffix(".exe")


def _strip_outer_quotes(value: str) -> str:
    """Remove one layer of balanced quotes left by Windows shlex splitting."""

    while len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def _command_path_argument(token: str) -> str | None:
    """Return a path to validate when a token looks like a filesystem argument."""

    value = _strip_outer_quotes(token.strip())
    if not value:
        return None

    if value.startswith("-") and "=" in value:
        _, _, value = value.partition("=")
    elif value.startswith("@"):
        value = value[1:]
    if not value or value.startswith("-"):
        return None
    if value in {".", "--"}:
        return None
    if _FILE_URI.match(value):
        return value[7:]
    if value == ".." or value.startswith(("../", "./", "~/")):
        return value
    if value.startswith(("/", "\\")) or _PATH_DRIVE.match(value):
        return value
    if "/" in value or "\\" in value:
        return value

    try:
        path = Path(value)
        if path.is_symlink() or path.exists():
            return value
    except OSError:
        return None
    return None


def _has_inline_code(exe_name: str, tokens: list[str]) -> bool:
    """Detect interpreter flags such as ``python -c`` or ``node -e``."""

    if exe_name == "deno" and len(tokens) > 1 and _strip_outer_quotes(tokens[1]) == "eval":
        return True
    eval_flags = _INLINE_EVAL_FLAGS.get(exe_name, set())
    option_values = _OPTIONS_WITH_VALUES.get(exe_name, set())
    stdin_code = exe_name in _STDIN_CODE_COMMANDS
    if _PYTHON_EXECUTABLE.fullmatch(exe_name):
        eval_flags = _INLINE_EVAL_FLAGS["python"]
        option_values = _OPTIONS_WITH_VALUES["python"]
        stdin_code = True
    index = 1
    while index < len(tokens):
        option = _strip_outer_quotes(tokens[index])
        if option in eval_flags:
            return True
        if "=" in option and option.partition("=")[0] in eval_flags:
            return True
        if any(option.startswith(flag) and flag.startswith("-") and not flag.startswith("--") for flag in eval_flags):
            return True
        if stdin_code and option == "-":
            return True
        if option == "-m" and exe_name in {"py", "python", "python3", "pythonw"}:
            return False
        if option in option_values:
            index += 2
            continue
        if not option.startswith("-"):
            return False
        index += 1
    return False


class ShellPolicy:
    """Decide whether a process command may run inside an agent session."""

    def __init__(self, extra_deny_terms: Iterable[str] = ()) -> None:
        self.extra_deny_terms = frozenset(term.lower() for term in extra_deny_terms)

    def validate(self, command: str) -> str:
        """Return the validated command or raise :class:`SecurityError`."""

        stripped = command.strip()
        if not stripped:
            raise SecurityError("Empty shell command")
        lower = stripped.lower()
        if any(pattern.search(lower) for pattern in DANGEROUS_PATTERNS):
            raise SecurityError("Command matches a dangerous shell pattern")
        tokens = shlex.split(stripped, posix=os.name != "nt")
        if not tokens:
            raise SecurityError("Empty shell command")
        exe_name = _command_name(tokens[0])
        if exe_name in FORBIDDEN_COMMANDS or exe_name in self.extra_deny_terms:
            raise SecurityError(f"Command is forbidden by shell policy: {exe_name}")
        if exe_name in _SHELL_WRAPPERS:
            raise SecurityError(f"Command launches a shell wrapper: {exe_name}")
        if _has_inline_code(exe_name, tokens):
            raise SecurityError("Command uses inline code execution and is forbidden")
        return stripped


def is_binary(data: bytes) -> bool:
    """Heuristic binary detection using NUL bytes and control characters."""

    if b"\x00" in data[:8192]:
        return True
    sample = data[:8192]
    control = sum(byte < 9 or 13 < byte < 32 for byte in sample)
    return bool(sample) and control / len(sample) > 0.3
