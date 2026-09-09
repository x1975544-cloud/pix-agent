from __future__ import annotations

import os
import shutil
import subprocess

import pytest
from pix.errors import SandboxTimeoutError
from pix.sandbox import DockerSandbox

pytestmark = [pytest.mark.integration]

_IMAGE = os.getenv("PIX_SANDBOX_IMAGE", "python:3.12-slim")


def _docker_ready() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        version = subprocess.run(
            [docker, "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if version.returncode != 0:
            return False
        image = subprocess.run(
            [docker, "image", "inspect", _IMAGE],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if image.returncode == 0:
            return True
        if os.getenv("PIX_SANDBOX_PULL_IMAGE") == "1":
            pulled = subprocess.run(
                [docker, "pull", _IMAGE],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            return pulled.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
    return False


def _make_sandbox() -> DockerSandbox:
    return DockerSandbox(image=_IMAGE)


@pytest.mark.skipif(not _docker_ready(), reason="Docker and the sandbox image are required")
def test_docker_sandbox_runs_workspace_process_as_nonroot(tmp_path):
    os.chmod(tmp_path, 0o777)
    (tmp_path / "probe.py").write_text(
        "from pathlib import Path\n"
        "import os\n"
        "Path('created.txt').write_text('docker wrote this', encoding='utf-8')\n"
        "print(f'uid={os.getuid()}')\n",
        encoding="utf-8",
    )

    result = _make_sandbox().run(["python", "-B", "probe.py"], workspace=tmp_path, timeout=30)

    assert result.success
    assert "uid=65534" in result.stdout
    assert (tmp_path / "created.txt").read_text(encoding="utf-8") == "docker wrote this"


@pytest.mark.skipif(not _docker_ready(), reason="Docker and the sandbox image are required")
def test_docker_sandbox_captures_process_exit_code(tmp_path):
    result = _make_sandbox().run(
        ["python", "-B", "-c", "raise SystemExit(7)"],
        workspace=tmp_path,
        timeout=30,
    )

    assert result.return_code == 7
    assert not result.success


@pytest.mark.skipif(not _docker_ready(), reason="Docker and the sandbox image are required")
def test_docker_sandbox_blocks_network_by_default(tmp_path):
    script = (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
        "except OSError:\n"
        "    print('network blocked')\n"
        "else:\n"
        "    raise SystemExit(11)\n"
    )

    result = _make_sandbox().run(["python", "-B", "-c", script], workspace=tmp_path, timeout=30)

    assert result.success
    assert "network blocked" in result.stdout


@pytest.mark.skipif(not _docker_ready(), reason="Docker and the sandbox image are required")
def test_docker_sandbox_stops_timed_out_process(tmp_path):
    with pytest.raises(SandboxTimeoutError, match="timed out"):
        _make_sandbox().run(
            ["python", "-B", "-c", "import time; time.sleep(30)"],
            workspace=tmp_path,
            timeout=1,
        )
