from __future__ import annotations

import json
from functools import lru_cache

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.api.dependencies import (
    CsrfContextDep,
    CurrentUserDep,
    DbDep,
    SettingsDep,
)
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import TestSession, User
from app.schemas.core import (
    DeleteConfirmation,
    HeaderPair,
    TestSessionCreate,
    TestSessionRead,
    TestSessionSecretReplace,
    TestSessionUpdate,
)
from app.security.crypto import KeyRing
from app.services.authorization import project_for_user, target_for_user

router = APIRouter(tags=["test sessions"])

RESERVED_HEADERS = {
    "host",
    "content-length",
    "transfer-encoding",
    "connection",
    "proxy-authorization",
    "proxy-authenticate",
    "upgrade",
    "keep-alive",
    "te",
    "trailer",
    "cookie",
    "authorization",
}


@lru_cache
def _keyring(active: str, old: str) -> KeyRing:
    return KeyRing.from_settings(active, old)


def _validate_custom_headers(headers: list[HeaderPair]) -> list[list[str]]:
    normalized: list[list[str]] = []
    seen: set[str] = set()
    for header in headers:
        name = header.name.lower()
        if name in RESERVED_HEADERS:
            raise ApiProblem(
                422,
                "reserved_header",
                f"The {header.name} header must use its dedicated field or is not allowed.",
            )
        if name in seen:
            raise ApiProblem(422, "duplicate_header", "Custom header names must be unique.")
        if "\r" in header.value or "\n" in header.value:
            raise ApiProblem(422, "header_injection", "Header values cannot contain line breaks.")
        seen.add(name)
        normalized.append([header.name, header.value])
    return normalized


def _secret_bytes(
    cookie_header: str | None,
    authorization_header: str | None,
    custom_headers: list[list[str]],
) -> bytes:
    if not cookie_header and not authorization_header and not custom_headers:
        raise ApiProblem(
            422, "session_secret_required", "At least one authentication value is required."
        )
    return json.dumps(
        {
            "cookie": cookie_header or "",
            "authorization": authorization_header or "",
            "custom_headers": custom_headers,
        },
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _session_aad(session: TestSession, field: str) -> str:
    return f"test_session:{session.project_id}:{session.target_id}:{session.id}:{field}"


async def _encrypt_session_values(
    session: TestSession,
    settings: SettingsDep,
    cookie_header: str | None,
    authorization_header: str | None,
    custom_headers: list[HeaderPair],
) -> None:
    normalized_custom = _validate_custom_headers(custom_headers)
    combined = _secret_bytes(cookie_header, authorization_header, normalized_custom)
    ring = _keyring(settings.encryption_master_key, settings.encryption_old_keys)
    if cookie_header:
        session.encrypted_cookie_data = ring.encrypt(
            cookie_header.encode(), _session_aad(session, "cookie")
        )
    else:
        session.encrypted_cookie_data = None
    if authorization_header:
        session.encrypted_authorization_header = ring.encrypt(
            authorization_header.encode(), _session_aad(session, "authorization")
        )
    else:
        session.encrypted_authorization_header = None
    if normalized_custom:
        session.encrypted_custom_headers = ring.encrypt(
            json.dumps(normalized_custom, separators=(",", ":")).encode(),
            _session_aad(session, "custom_headers"),
        )
    else:
        session.encrypted_custom_headers = None
    session.secret_fingerprint = ring.fingerprint(combined)


async def _session(db: DbDep, user: User, session_id: str) -> TestSession:
    session = await db.get(TestSession, session_id)
    if session is None:
        raise ApiProblem(404, "session_not_found", "The test session was not found.")
    await project_for_user(db, user, session.project_id)
    return session


@router.get("/projects/{project_id}/sessions", response_model=list[TestSessionRead])
async def list_sessions(project_id: str, db: DbDep, _user: CurrentUserDep) -> list[TestSessionRead]:
    await project_for_user(db, _user, project_id)
    sessions = (
        (
            await db.execute(
                select(TestSession)
                .where(TestSession.project_id == project_id)
                .order_by(TestSession.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [TestSessionRead.model_validate(session) for session in sessions]


@router.post(
    "/projects/{project_id}/sessions",
    response_model=TestSessionRead,
    status_code=201,
)
async def create_session(
    project_id: str,
    payload: TestSessionCreate,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> TestSessionRead:
    await project_for_user(db, context.user, project_id)
    target = await target_for_user(db, context.user, payload.target_id)
    if target.project_id != project_id:
        raise ApiProblem(404, "target_not_found", "The target was not found in this project.")
    if not target.authorization_confirmed:
        raise ApiProblem(
            400,
            "target_not_authorized",
            "Target authorization is required before storing a test session.",
        )
    session = TestSession(
        project_id=project_id,
        target_id=target.id,
        name=payload.name.strip(),
        role_label=payload.role_label.strip(),
        description=payload.description,
        secret_fingerprint=("anonymous" if payload.is_anonymous else "not-yet-derived"),
        is_anonymous=payload.is_anonymous,
        credential_version=1,
        expires_at=payload.expires_at,
        is_active=True,
        created_by=context.user.id,
    )
    db.add(session)
    await db.flush()
    if payload.is_anonymous:
        if payload.cookie_header or payload.authorization_header or payload.custom_headers:
            raise ApiProblem(
                422,
                "anonymous_profile_has_credentials",
                "Anonymous profiles cannot contain credential values.",
            )
    else:
        await _encrypt_session_values(
            session,
            settings,
            payload.cookie_header,
            payload.authorization_header,
            payload.custom_headers,
        )
    await record_audit(
        db,
        request,
        action="test_session_created",
        entity_type="test_session",
        entity_id=session.id,
        user_id=context.user.id,
        summary=f"Created a masked test session for role {session.role_label}.",
    )
    await db.commit()
    await db.refresh(session)
    return TestSessionRead.model_validate(session)


@router.get("/sessions/{session_id}", response_model=TestSessionRead)
async def get_session(session_id: str, db: DbDep, _user: CurrentUserDep) -> TestSessionRead:
    return TestSessionRead.model_validate(await _session(db, _user, session_id))


@router.patch("/sessions/{session_id}", response_model=TestSessionRead)
async def update_session(
    session_id: str,
    payload: TestSessionUpdate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> TestSessionRead:
    session = await _session(db, context.user, session_id)
    if session.is_anonymous:
        raise ApiProblem(
            409,
            "anonymous_profile_has_no_secret",
            "Anonymous profiles do not have replaceable credentials.",
        )
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(session, key, value)
    await record_audit(
        db,
        request,
        action="test_session_updated",
        entity_type="test_session",
        entity_id=session.id,
        user_id=context.user.id,
        summary="Updated test-session metadata without exposing credentials.",
    )
    await db.commit()
    await db.refresh(session)
    return TestSessionRead.model_validate(session)


@router.post("/sessions/{session_id}/replace-secret", response_model=TestSessionRead)
async def replace_session_secret(
    session_id: str,
    payload: TestSessionSecretReplace,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> TestSessionRead:
    session = await _session(db, context.user, session_id)
    await _encrypt_session_values(
        session,
        settings,
        payload.cookie_header,
        payload.authorization_header,
        payload.custom_headers,
    )
    session.credential_version += 1
    session.is_active = True
    await record_audit(
        db,
        request,
        action="test_session_secret_replaced",
        entity_type="test_session",
        entity_id=session.id,
        user_id=context.user.id,
        summary="Replaced test-session credentials; previous values were not exposed.",
    )
    await db.commit()
    await db.refresh(session)
    return TestSessionRead.model_validate(session)


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def delete_session(
    session_id: str,
    payload: DeleteConfirmation,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> None:
    session = await _session(db, context.user, session_id)
    if payload.confirmation != session.name:
        raise ApiProblem(
            400, "confirmation_mismatch", "Type the exact session name to confirm deletion."
        )
    session_name = session.name
    await db.delete(session)
    await record_audit(
        db,
        request,
        action="test_session_deleted",
        entity_type="test_session",
        entity_id=session_id,
        user_id=context.user.id,
        summary=f"Deleted test session {session_name}.",
    )
    await db.commit()
