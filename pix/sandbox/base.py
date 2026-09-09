"""Sandbox abstraction shared by all execution boundaries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Captured result of one process run inside a sandbox."""

    return_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return self.return_code == 0

    @property
    def exit_code(self) -> int:
        """Compatibility alias for consumers that use ``exit_code``."""

        return self.return_code


class Sandbox(ABC):
    """Boundary that runs workspace processes in isolation."""

    @abstractmethod
    def run(
        self,
        command: str | list[str] | tuple[str, ...],
        *,
        workspace: str | Path,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """Run one process and return its output or raise a sandbox error."""
