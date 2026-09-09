from __future__ import annotations

import subprocess

import pytest
from pix.errors import SandboxError, SandboxTimeoutError, SandboxUnavailableError
from pix.sandbox import DockerSandbox, SandboxLimits
from pix.sandbox import docker as docker_module


def _fake_runner(monkeypatch: pytest.MonkeyPatch, calls: list[list[str]]) -> None:
    def runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[1] == "version":
            return subprocess.CompletedProcess(argv, 0, "29.7.2\n", "")
        if argv[1] == "rm":
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, "hello from docker\n", "")

    monkeypatch.setattr(docker_module, "_run_command", runner)


def test_docker_sandbox_runs_command_in_container(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    _fake_runner(monkeypatch, calls)
    sandbox = DockerSandbox(image="python:3.12-slim")

    result = sandbox.run("python hello.py", workspace=tmp_path, timeout=10)

    assert result.success
    assert result.stdout.strip() == "hello from docker"
    run = next(argv for argv in calls if argv[1] == "run")
    assert run[-3:] == ["python:3.12-slim", "python", "hello.py"]


def test_docker_sandbox_defaults_are_hardened(tmp_path):
    sandbox = DockerSandbox()
    argv = sandbox._build_argv(
        ["python", "main.py"],
        tmp_path.resolve(),
        env=None,
        container_name="pix-sandbox-test",
    )

    assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
    assert "--user" in argv and argv[argv.index("--user") + 1] == "65534:65534"
    assert "--security-opt" in argv and "no-new-privileges" in argv
    assert "--cap-drop" in argv and argv[argv.index("--cap-drop") + 1] == "ALL"
    mounts = [argv[index + 1] for index, flag in enumerate(argv) if flag == "--mount"]
    assert len(mounts) == 1
    assert mounts[0].startswith("type=bind,source=")
    assert mounts[0].endswith("target=/workspace")
    assert "/var/run/docker.sock" not in mounts
    assert "--device" not in argv
    assert "--privileged" not in argv
    assert not any(mount.startswith("source=/") for mount in mounts)


def test_docker_sandbox_can_opt_into_network_and_readonly_workspace(tmp_path):
    sandbox = DockerSandbox(network_enabled=True, read_only_workspace=True)
    argv = sandbox._build_argv(
        ["python", "main.py"],
        tmp_path.resolve(),
        env=None,
        container_name="pix-sandbox-test",
    )

    assert "--network" not in argv
    mount = argv[argv.index("--mount") + 1]
    assert mount.endswith("target=/workspace,readonly")


def test_docker_sandbox_applies_resource_limits(tmp_path):
    sandbox = DockerSandbox(
        limits=SandboxLimits(
            cpus=1.5,
            memory_bytes=128 * 1024 * 1024,
            max_processes=32,
        )
    )
    argv = sandbox._build_argv(
        ["python", "main.py"],
        tmp_path.resolve(),
        env=None,
        container_name="pix-sandbox-test",
    )

    assert argv[argv.index("--cpus") + 1] == "1.5"
    assert argv[argv.index("--memory") + 1] == "134217728"
    assert argv[argv.index("--memory-swap") + 1] == "134217728"
    assert argv[argv.index("--pids-limit") + 1] == "32"


def test_docker_sandbox_passes_explicit_env(tmp_path):
    sandbox = DockerSandbox()
    argv = sandbox._build_argv(
        ["python", "main.py"],
        tmp_path.resolve(),
        env={"B": "2", "A": "1"},
        container_name="pix-sandbox-test",
    )

    env_flags = [argv[index + 1] for index, flag in enumerate(argv) if flag == "--env"]
    assert env_flags == ["A=1", "B=2"]


def test_docker_sandbox_captures_nonzero_exit(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[1] == "version":
            return subprocess.CompletedProcess(argv, 0, "29.7.2\n", "")
        return subprocess.CompletedProcess(argv, 7, "stdout", "stderr")

    monkeypatch.setattr(docker_module, "_run_command", runner)
    result = DockerSandbox().run(["python", "exit.py"], workspace=tmp_path)

    assert result.return_code == 7
    assert result.stdout == "stdout"
    assert result.stderr == "stderr"
    assert not result.success


def test_docker_sandbox_timeout_removes_container(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[1] == "version":
            return subprocess.CompletedProcess(argv, 0, "29.7.2\n", "")
        if argv[1] == "rm":
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise subprocess.TimeoutExpired(argv, timeout)

    monkeypatch.setattr(docker_module, "_run_command", runner)
    with pytest.raises(SandboxTimeoutError, match="timed out"):
        DockerSandbox().run(["python", "slow.py"], workspace=tmp_path, timeout=0.1)

    assert any(argv[1] == "rm" for argv in calls)


def test_docker_sandbox_reports_unavailable_daemon(monkeypatch):
    def runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "", "Cannot connect to the Docker daemon")

    monkeypatch.setattr(docker_module, "_run_command", runner)
    sandbox = DockerSandbox()

    assert not sandbox.is_available()
    with pytest.raises(SandboxUnavailableError, match="daemon did not respond"):
        sandbox.run(["python", "main.py"], workspace=".")


def test_docker_sandbox_reports_missing_cli(monkeypatch):
    def runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("docker")

    monkeypatch.setattr(docker_module, "_run_command", runner)

    with pytest.raises(SandboxUnavailableError, match="could not run the docker CLI"):
        DockerSandbox().run(["python", "main.py"], workspace=".")


def test_docker_sandbox_validates_workspace_and_command(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    _fake_runner(monkeypatch, calls)
    sandbox = DockerSandbox()

    with pytest.raises(SandboxError, match="does not exist"):
        sandbox.run(["python", "main.py"], workspace=tmp_path / "missing")
    with pytest.raises(SandboxError, match="empty command"):
        sandbox.run([], workspace=tmp_path)
    with pytest.raises(ValueError, match="timeout"):
        sandbox.run(["python", "main.py"], workspace=tmp_path, timeout=0)
