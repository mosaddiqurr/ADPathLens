from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

AUTHORIZATION_ACKNOWLEDGEMENT = (
    "I confirm that I own this target or have explicit authorization to test it."
)


@pytest.fixture
async def client(tmp_path) -> AsyncIterator[httpx.AsyncClient]:  # type: ignore[no-untyped-def]
    database = tmp_path / "integration.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    await engine.dispose()


async def preauth_csrf(client: httpx.AsyncClient) -> str:
    response = await client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


async def setup_admin(client: httpx.AsyncClient) -> str:
    token = await preauth_csrf(client)
    response = await client.post(
        "/api/v1/auth/setup",
        headers={"X-CSRF-Token": token},
        json={
            "setup_token": "development-setup-token",
            "email": "authzdiff.admin@example.com",
            "display_name": "Test Administrator",
            "password": "correct horse battery staple",
            "authorization_acknowledgement": AUTHORIZATION_ACKNOWLEDGEMENT,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["csrf_token"])


@pytest.mark.asyncio
async def test_csrf_is_required_for_authenticated_mutations(
    client: httpx.AsyncClient,
) -> None:
    await setup_admin(client)
    denied = await client.post(
        "/api/v1/projects",
        json={"name": "Missing CSRF", "description": ""},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "csrf_failed"
    assert "correct horse battery staple" not in denied.text


@pytest.mark.asyncio
async def test_failed_login_is_generic_and_audited_as_denied(
    client: httpx.AsyncClient,
) -> None:
    await setup_admin(client)
    failed_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost",
    )
    try:
        token = await preauth_csrf(failed_client)
        failed = await failed_client.post(
            "/api/v1/auth/login",
            headers={"X-CSRF-Token": token},
            json={
                "email": "authzdiff.admin@example.com",
                "password": "incorrect synthetic password",
            },
        )
        assert failed.status_code == 401
        assert failed.json()["code"] == "invalid_credentials"
        assert "incorrect synthetic password" not in failed.text
        audit = await client.get("/api/v1/audit-events?action=login_failure")
        assert audit.status_code == 200
        events = audit.json()
        assert len(events) == 1
        assert events[0]["outcome"] == "denied"
    finally:
        await failed_client.aclose()


@pytest.mark.asyncio
async def test_profile_secrets_are_write_only_and_projects_are_isolated(
    client: httpx.AsyncClient,
) -> None:
    admin_csrf = await setup_admin(client)
    project_response = await client.post(
        "/api/v1/projects",
        headers={"X-CSRF-Token": admin_csrf},
        json={"name": "Administrator project", "description": "Owner-only fixture."},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    target_response = await client.post(
        f"/api/v1/projects/{project_id}/targets",
        headers={"X-CSRF-Token": admin_csrf},
        json={
            "name": "Authorized HTTPS fixture",
            "base_url": "https://example.invalid",
            "allowed_path_prefixes": ["/"],
            "allowed_methods": ["GET"],
        },
    )
    assert target_response.status_code == 201, target_response.text
    target_id = target_response.json()["id"]
    confirmation = await client.post(
        f"/api/v1/targets/{target_id}/confirm-authorization",
        headers={"X-CSRF-Token": admin_csrf},
        json={"acknowledgement": AUTHORIZATION_ACKNOWLEDGEMENT},
    )
    assert confirmation.status_code == 200
    secret = "Bearer integration-fixture-secret-never-return"  # noqa: S105
    profile_response = await client.post(
        f"/api/v1/projects/{project_id}/sessions",
        headers={"X-CSRF-Token": admin_csrf},
        json={
            "target_id": target_id,
            "name": "Administrator fixture profile",
            "role_label": "administrator",
            "authorization_header": secret,
            "custom_headers": [],
        },
    )
    assert profile_response.status_code == 201, profile_response.text
    profile_payload = profile_response.json()
    assert profile_payload["secret_fingerprint"].startswith("hmac:")
    assert "authorization_header" not in profile_payload
    assert "encrypted_authorization_header" not in profile_payload
    assert "integration-fixture-secret-never-return" not in profile_response.text
    listed = await client.get(f"/api/v1/projects/{project_id}/sessions")
    assert secret not in listed.text
    report_response = await client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers={"X-CSRF-Token": admin_csrf},
        json={"format": "json"},
    )
    assert report_response.status_code == 201, report_response.text
    report_id = report_response.json()["id"]
    report_download = await client.get(f"/api/v1/reports/{report_id}/download")
    assert report_download.status_code == 200
    assert report_download.headers["content-type"].startswith("application/json")
    assert secret.encode() not in report_download.content

    created_user = await client.post(
        "/api/v1/users",
        headers={"X-CSRF-Token": admin_csrf},
        json={
            "email": "authzdiff.analyst@example.com",
            "display_name": "Other Analyst",
            "initial_password": "temporary analyst password",
            "role": "analyst",
        },
    )
    assert created_user.status_code == 201

    other = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost",
    )
    try:
        login_csrf = await preauth_csrf(other)
        login = await other.post(
            "/api/v1/auth/login",
            headers={"X-CSRF-Token": login_csrf},
            json={
                "email": "authzdiff.analyst@example.com",
                "password": "temporary analyst password",
            },
        )
        assert login.status_code == 200
        assert login.json()["user"]["must_change_password"] is True
        session_csrf = login.json()["csrf_token"]
        required = await other.get("/api/v1/projects")
        assert required.status_code == 403
        assert required.json()["code"] == "password_change_required"
        rejected_change = await other.post(
            "/api/v1/auth/change-password",
            headers={"X-CSRF-Token": session_csrf},
            json={
                "current_password": "incorrect temporary password",
                "new_password": "permanent analyst password",
            },
        )
        assert rejected_change.status_code == 400
        assert rejected_change.json()["code"] == "current_password_invalid"
        still_required = await other.get("/api/v1/projects")
        assert still_required.status_code == 403
        assert still_required.json()["code"] == "password_change_required"
        changed = await other.post(
            "/api/v1/auth/change-password",
            headers={"X-CSRF-Token": session_csrf},
            json={
                "current_password": "temporary analyst password",
                "new_password": "permanent analyst password",
            },
        )
        assert changed.status_code == 200
        assert changed.json()["user"]["must_change_password"] is False
        assert changed.json()["csrf_token"] != session_csrf
        forbidden = await other.get(f"/api/v1/projects/{project_id}")
        assert forbidden.status_code == 404
        assert forbidden.json()["code"] == "project_not_found"
        cross_profile = await other.get(f"/api/v1/sessions/{profile_payload['id']}")
        assert cross_profile.status_code == 404
        cross_report = await other.get(f"/api/v1/reports/{report_id}")
        assert cross_report.status_code == 404
        cross_download = await other.get(f"/api/v1/reports/{report_id}/download")
        assert cross_download.status_code == 404
    finally:
        await other.aclose()
