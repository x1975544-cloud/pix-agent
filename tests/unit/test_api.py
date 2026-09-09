from __future__ import annotations

from fastapi.testclient import TestClient
from pix.api.app import create_app
from pix.config.settings import Settings


def test_health_and_catalog(tmp_path):
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{tmp_path}/api.db",
        workspace=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
    )
    application = create_app(settings)
    with TestClient(application) as client:
        assert client.get("/health").json()["status"] == "ok"
        tools = client.get("/api/tools").json()
        names = {tool["name"] for tool in tools}
        assert {"read_file", "write_file", "run_shell", "git_status"} <= names
        assert client.get("/api/skills").status_code == 200
