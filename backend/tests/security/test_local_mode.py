import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from tests.test_imports import authenticated_project


def test_local_session_keeps_csrf_role_and_origin_boundaries(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "local_mode", True)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50123)) as local:
        assert local.get("/api/v1/auth/local-status").json() == {"available": True}
        assert local.post("/api/v1/auth/local-session").status_code == 403
        assert (
            local.post(
                "/api/v1/auth/local-session", headers={"X-ADPathLens-Local": "1", "Origin": "https://untrusted.example"}
            ).status_code
            == 403
        )
        assert (
            local.post(
                "/api/v1/auth/local-session", headers={"X-ADPathLens-Local": "1", "Sec-Fetch-Site": "cross-site"}
            ).status_code
            == 403
        )
        session = local.post("/api/v1/auth/local-session", headers={"X-ADPathLens-Local": "1"})
        assert session.status_code == 200, session.text
        assert session.json()["user"]["role"] == "analyst"
        assert "httponly" in session.headers["set-cookie"].lower()
        assert local.get("/api/v1/auth/me").status_code == 200
        assert local.post("/api/v1/workspaces", json={"name": "Should be rejected"}).status_code == 403
        assert local.get("/api/v1/system/status").status_code == 403
        reopened = local.post("/api/v1/auth/local-session", headers={"X-ADPathLens-Local": "1"})
        assert reopened.json()["user"]["id"] == session.json()["user"]["id"]
    assert client.get("/api/v1/auth/local-status").json() == {"available": False}
    assert client.post("/api/v1/auth/local-session", headers={"X-ADPathLens-Local": "1"}).status_code == 403


def test_local_mode_does_not_take_over_existing_account_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticated_project(client)
    monkeypatch.setattr(get_settings(), "local_mode", True)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50123)) as local:
        response = local.post("/api/v1/auth/local-session", headers={"X-ADPathLens-Local": "1"})
        assert response.status_code == 409
        assert response.json()["code"] == "local_database"


def test_local_mode_cannot_be_enabled_for_production() -> None:
    with pytest.raises(RuntimeError, match="LOCAL_MODE"):
        Settings(app_env="production", local_mode=True).validate_production()
