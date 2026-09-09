"""Docker-backed workspace process sandbox."""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from pix.errors import SandboxError, SandboxTimeoutError, SandboxUnavailableError
from pix.sandbox.base import Sandbox, SandboxResult

DEFAULT_SANDBOX_IMAGE = "python:3.12-slim"
DEFAULT_SANDBOX_USER = "65534:65534"
DEFAULT_WORKSPACE_MOUNT_PATH = "/workspace"
_CONTAINER_NAME_PREFIX = "pix-sandbox-"


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    """Container resource limits applied to every sandboxed process run."""

    cpus: float | None = None
    memory_bytes: int | None = None
    max_processes: int | None = None

    def __post_init__(self) -> None:
        if self.cpus is not None and self.cpus <= 0:
            raise ValueError("cpus must be greater than zero")
        if self.memory_bytes is not None and self.memory_bytes <= 0:
            raise ValueError("memory_bytes must be greater than zero")
        if self.max_processes is not None and self.max_processes <= 0:
            raise ValueError("max_processes must be greater than zero")


@dataclass(frozen=True, slots=True)
class DockerSandboxConfig:
    """Immutable defaults for one :class:`DockerSandbox` instance."""

    image: str = DEFAULT_SANDBOX_IMAGE
    workspace_mount_path: str = DEFAULT_WORKSPACE_MOUNT_PATH
    user: str = DEFAULT_SANDBOX_USER
    read_only_workspace: bool = False
    network_enabled: bool = False
    limits: SandboxLimits = field(default_factory=SandboxLimits)
    docker_executable: str = "docker"

    def __post_init__(self) -> None:
        if not self.image:
            raise ValueError("Docker image cannot be empty")
        if not self.workspace_mount_path.startswith("/"):
            raise ValueError("workspace_mount_path must be an absolute container path")
        if not self.user:
            raise ValueError("container user cannot be empty")
        if not self.docker_executable:
            raise ValueError("docker_executable cannot be empty")


def _run_command(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    """Run one docker CLI command with bounded output capture."""

    return subprocess.run(
        argv,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=timeout,
    )


def _parse_command(command: str | list[str] | tuple[str, ...]) -> list[str]:
    """Normalize a command line or argv list into docker argv."""

    tokens = shlex.split(command, posix=True) if isinstance(command, str) else list(command)
    if not tokens:
        raise SandboxError("Cannot run an empty command")
    return [str(token) for token in tokens]


class DockerSandbox(Sandbox):
    """Execute workspace processes in a short-lived, hardened Docker container.

    A fresh container is created for each run and removed when the command
    exits. Only the supplied workspace is bound into the container; Docker
    socket access, extra host mounts, devices and the default bridge network
    are intentionally not configured.
    """

    def __init__(
        self,
        *,
        image: str = DEFAULT_SANDBOX_IMAGE,
        workspace_mount_path: str = DEFAULT_WORKSPACE_MOUNT_PATH,
        user: str = DEFAULT_SANDBOX_USER,
        read_only_workspace: bool = False,
        network_enabled: bool = False,
        limits: SandboxLimits | None = None,
        docker_executable: str = "docker",
    ) -> None:
        self.config = DockerSandboxConfig(
            image=image,
            workspace_mount_path=workspace_mount_path,
            user=user,
            read_only_workspace=read_only_workspace,
            network_enabled=network_enabled,
            limits=limits or SandboxLimits(),
            docker_executable=docker_executable,
        )

    @property
    def limits(self) -> SandboxLimits:
        return self.config.limits

    def is_available(self) -> bool:
        """Return whether the configured docker daemon is reachable."""

        try:
            self._require_available()
            return True
        except SandboxUnavailableError:
            return False

    def run(
        self,
        command: str | list[str] | tuple[str, ...],
        *,
        workspace: str | Path,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        self._require_available()
        workspace_path = self._resolve_workspace(workspace)
        tokens = _parse_command(command)
        self._validate_timeout(timeout)
        if env is not None:
            self._validate_env(env)

        container_name = f"{_CONTAINER_NAME_PREFIX}{uuid4().hex}"
        argv = self._build_argv(
            tokens,
            workspace_path,
            env=env,
            container_name=container_name,
        )
        started = time.perf_counter()
        try:
            completed = _run_command(argv, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self._remove_container(container_name)
            raise SandboxTimeoutError(f"Workspace process timed out after {timeout:g}s in Docker sandbox") from exc
        except OSError as exc:
            self._remove_container(container_name)
            raise SandboxError(f"Failed to run Docker sandbox command: {exc}") from exc
        duration = time.perf_counter() - started
        return SandboxResult(
            return_code=int(completed.returncode),
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_seconds=duration,
        )

    def _build_argv(
        self,
        command: list[str],
        workspace: Path,
        *,
        env: dict[str, str] | None,
        container_name: str,
    ) -> list[str]:
        argv = [
            self.config.docker_executable,
            "run",
            "--rm",
            "--name",
            container_name,
        ]
        if not self.config.network_enabled:
            argv += ["--network", "none"]
        argv += [
            "--user",
            self.config.user,
            "--workdir",
            self.config.workspace_mount_path,
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
        ]
        mount = f"type=bind,source={workspace},target={self.config.workspace_mount_path}"
        if self.config.read_only_workspace:
            mount += ",readonly"
        argv += ["--mount", mount]

        if env:
            for key in sorted(env):
                argv += ["--env", f"{key}={env[key]}"]
        if self.limits.cpus is not None:
            argv += ["--cpus", f"{self.limits.cpus:g}"]
        if self.limits.memory_bytes is not None:
            memory = str(self.limits.memory_bytes)
            argv += ["--memory", memory, "--memory-swap", memory]
        if self.limits.max_processes is not None:
            argv += ["--pids-limit", str(self.limits.max_processes)]

        argv += [self.config.image, *command]
        return argv

    def _resolve_workspace(self, workspace: str | Path) -> Path:
        path = Path(workspace).expanduser().resolve()
        if not path.exists():
            raise SandboxError(f"Workspace does not exist: {path}")
        if not path.is_dir():
            raise SandboxError(f"Workspace is not a directory: {path}")
        return path

    def _require_available(self) -> None:
        argv = [
            self.config.docker_executable,
            "version",
            "--format",
            "{{.Server.Version}}",
        ]
        try:
            completed = _run_command(argv, timeout=5.0)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SandboxUnavailableError(
                "Docker sandbox is unavailable: could not run the docker CLI. "
                "Install Docker and make sure the daemon is started."
            ) from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip().splitlines()[-1] if completed.stderr else "unknown error"
            raise SandboxUnavailableError(
                "Docker sandbox is unavailable: "
                f"the Docker daemon did not respond ({detail}). "
                "Install Docker and make sure the daemon is started."
            )

    def _remove_container(self, container_name: str) -> None:
        argv = [self.config.docker_executable, "rm", "--force", container_name]
        try:
            _run_command(argv, timeout=5.0)
        except (OSError, subprocess.TimeoutExpired):
            return

    @staticmethod
    def _validate_timeout(timeout: float) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

    @staticmethod
    def _validate_env(env: dict[str, str]) -> None:
        for key, value in env.items():
            if not key or "\n" in key or "\n" in value:
                raise ValueError("Docker environment variables cannot be empty or contain newlines")
