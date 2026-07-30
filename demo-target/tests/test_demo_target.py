import os
import subprocess
import sys

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.main import app
from app.store import reset_fixtures

ADMIN = {"Authorization": "Bearer demo-admin-token"}
USER_A = {"Authorization": "Bearer demo-user-a-token"}
USER_B = {"Authorization": "Bearer demo-user-b-token"}


def setup_function() -> None:
    reset_fixtures()


async def request(method: str, path: str, **kwargs: object) -> Response:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://demo-target",
    ) as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.asyncio
async def test_health_and_readiness() -> None:
    assert (await request("GET", "/health")).json()["status"] == "ok"
    assert (await request("GET", "/ready")).json()["status"] == "ready"


@pytest.mark.asyncio
async def test_secure_vertical_endpoint_denies_regular_user() -> None:
    assert (await request("GET", "/secure/authenticated")).status_code == 401
    assert (
        await request("GET", "/secure/admin/users", headers=ADMIN)
    ).status_code == 200
    assert (
        await request("GET", "/secure/admin/users", headers=USER_A)
    ).status_code == 403


@pytest.mark.asyncio
async def test_vulnerable_vertical_endpoint_returns_same_listing() -> None:
    high = await request("GET", "/vulnerable/admin/users", headers=ADMIN)
    low = await request("GET", "/vulnerable/admin/users", headers=USER_A)
    assert high.status_code == low.status_code == 200
    assert high.json() == low.json()


@pytest.mark.asyncio
async def test_secure_and_vulnerable_ownership_paths_differ() -> None:
    secure = await request("GET", "/secure/documents/doc-a", headers=USER_B)
    assert secure.status_code == 404
    exposed = await request("GET", "/vulnerable/documents/doc-a", headers=USER_B)
    assert exposed.status_code == 200
    assert exposed.json()["owner_id"] == "user-a"


@pytest.mark.asyncio
async def test_sensitive_method_and_existence_fixtures_have_secure_controls() -> None:
    secure_account = await request("GET", "/secure/accounts/user-a", headers=USER_A)
    exposed_account = await request(
        "GET", "/vulnerable/accounts/user-a", headers=USER_B
    )
    assert "national_id" not in secure_account.json()
    assert exposed_account.json()["national_id"].startswith("DEMO-")

    secure_delete = await request(
        "DELETE", "/secure/method-protection/documents/doc-a", headers=USER_A
    )
    vulnerable_delete = await request(
        "DELETE", "/vulnerable/method-protection/documents/doc-a", headers=USER_A
    )
    assert secure_delete.status_code == 403
    assert vulnerable_delete.status_code == 200

    hidden = await request("GET", "/secure/existence/documents/doc-a", headers=USER_B)
    leaked = await request(
        "GET", "/vulnerable/existence/documents/doc-a", headers=USER_B
    )
    missing = await request(
        "GET", "/vulnerable/existence/documents/missing", headers=USER_B
    )
    assert hidden.status_code == 404
    assert leaked.status_code == 403
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_state_change_fixture_can_be_reset_without_default_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = await request(
        "PATCH",
        "/vulnerable/profiles/user-a",
        headers=USER_B,
        json={"display_name": "Changed by User B"},
    )
    assert changed.status_code == 200
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_RESET_TOKEN", "test-reset")
    assert (
        await request(
            "POST",
            "/internal/reset",
            headers={"X-Demo-Reset-Token": "wrong"},
        )
    ).status_code == 403
    assert (
        await request(
            "POST",
            "/internal/reset",
            headers={"X-Demo-Reset-Token": "test-reset"},
        )
    ).status_code == 200
    restored = await request("GET", "/profiles/user-a", headers=USER_A)
    assert restored.json()["name"] == "Demo User A"


@pytest.mark.asyncio
async def test_reset_requires_explicit_demo_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.setenv("DEMO_RESET_TOKEN", "test-reset")
    denied = await request(
        "POST",
        "/internal/reset",
        headers={"X-Demo-Reset-Token": "test-reset"},
    )
    assert denied.status_code == 403


def test_demo_target_refuses_production_startup() -> None:
    environment = {**os.environ, "APP_ENV": "production"}
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "cannot run in production" in result.stderr
