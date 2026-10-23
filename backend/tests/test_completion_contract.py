from pathlib import Path

import pytest

from app.core.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "app_secret_key": "correct-horse-battery-staple-with-entropy-2026",
        "database_url": f"sqlite+aiosqlite:///{(Path(Path.cwd().anchor) / 'adpathlens' / 'production.db').as_posix()}",
        "session_cookie_secure": True,
        "allowed_frontend_origins": "https://adpathlens.example",
        "frontend_public_url": "https://adpathlens.example",
        "backend_public_url": "https://api.adpathlens.example",
        "report_storage_path": Path(Path.cwd().anchor) / "adpathlens" / "reports",
        "demo_mode": False,
        "e2e_mode": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("app_secret_key", "development-only-change-this-secret-key"),
        ("session_cookie_secure", False),
        ("allowed_frontend_origins", "*"),
        ("allowed_frontend_origins", "http://adpathlens.example"),
        ("demo_mode", True),
        ("e2e_mode", True),
        ("database_url", "sqlite+aiosqlite:///./production.db"),
        ("database_url", "sqlite+aiosqlite:///:memory:"),
        ("frontend_public_url", "http://adpathlens.example"),
        ("report_storage_path", Path("./relative-reports")),
    ],
)
def test_production_rejects_unsafe_combinations(field: str, value: object) -> None:
    settings = production_settings(**{field: value})
    with pytest.raises(RuntimeError):
        settings.validate_production()


def test_production_accepts_explicit_secure_configuration() -> None:
    production_settings().validate_production()


def test_cross_site_cookies_require_https() -> None:
    with pytest.raises(RuntimeError, match="SameSite=None"):
        Settings(session_cookie_samesite="none", session_cookie_secure=False).validate_production()
    production_settings(session_cookie_samesite="none").validate_production()
