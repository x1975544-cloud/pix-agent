from __future__ import annotations

from fastapi.testclient import TestClient
from pix.api.app import create_app
from pix.config.settings import Settings

API_TOKEN = "test-api-token"
API_HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


def _settings(tmp_path, *, workspace=None, api_token=API_TOKEN):
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{tmp_path}/api.db",
        workspace=str(workspace or tmp_path),
        skills_dir=str(tmp_path / "skills"),
        api_token=api_token,
    )


def test_health_and_catalog(tmp_path):
    settings = _settings(tmp_path)
    application = create_app(settings)
    with TestClient(application) as client:
        assert client.get("/health").json()["status"] == "ok"
        tools = client.get("/api/tools").json()
        names = {tool["name"] for tool in tools}
        assert {"read_file", "write_file", "run_shell", "git_status"} <= names
        assert client.get("/api/skills").status_code == 200


def test_protected_routes_require_api_token(tmp_path):
    application = create_app(_settings(tmp_path))
    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/sessions").status_code == 401
        assert client.get("/api/sessions/sess_1").status_code == 401
        assert client.get("/api/traces/sess_1").status_code == 401
        assert client.get("/api/traces/sess_1/stream").status_code == 401
        assert client.post("/api/agent/run", json={"task": "do it"}).status_code == 401


def test_api_rejects_invalid_bearer_token(tmp_path):
    application = create_app(_settings(tmp_path))
    with TestClient(application) as client:
        response = client.get("/api/sessions", headers={"Authorization": "Bearer wrong-token"})
        assert response.status_code == 401


def test_api_fails_closed_without_configured_token(tmp_path):
    application = create_app(_settings(tmp_path, api_token=None))
    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/sessions").status_code == 503
        assert client.post("/api/agent/run", json={"task": "do it"}).status_code == 503


def test_api_accepts_valid_token(tmp_path):
    application = create_app(_settings(tmp_path))
    with TestClient(application) as client:
        response = client.get("/api/sessions", headers=API_HEADERS)
        assert response.status_code == 200
        assert response.json() == []


def test_api_rejects_workspace_outside_configured_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    application = create_app(_settings(tmp_path, workspace=root))
    with TestClient(application) as client:
        response = client.post(
            "/api/agent/run",
            headers=API_HEADERS,
            json={"task": "inspect", "workspace": str(tmp_path)},
        )
        assert response.status_code == 400
        assert "PIX_WORKSPACE" in response.json()["detail"]

        traversal = client.post(
            "/api/agent/run",
            headers=API_HEADERS,
            json={"task": "inspect", "workspace": "../"},
        )
        assert traversal.status_code == 400


def test_api_rejects_missing_workspace_directory(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    application = create_app(_settings(tmp_path, workspace=root))
    with TestClient(application) as client:
        response = client.post(
            "/api/agent/run",
            headers=API_HEADERS,
            json={"task": "inspect", "workspace": "missing-project"},
        )
        assert response.status_code == 400
        assert "does not exist" in response.json()["detail"]
