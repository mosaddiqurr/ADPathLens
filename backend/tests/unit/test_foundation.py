from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import redact
from app.main import app


def test_health() -> None:
    client = TestClient(app, base_url="http://localhost")
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_recursive_redaction() -> None:
    value = {
        "authorization": "Bearer reusable",
        "nested": {"password": "bad", "safe": "visible"},
    }
    assert redact(value) == {
        "authorization": "[REDACTED]",
        "nested": {"password": "[REDACTED]", "safe": "visible"},
    }


def test_production_rejects_development_secrets() -> None:
    try:
        Settings(app_env="production", session_cookie_secure=True)
    except ValueError as exc:
        assert "production secrets" in str(exc)
    else:
        raise AssertionError("production configuration accepted development secrets")
