from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated

from anyio import to_thread
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, func, select

from app.api.dependencies import (
    AuthContext,
    CsrfContextDep,
    DbDep,
    PreauthCsrfDep,
    SettingsDep,
    current_auth_context,
    optional_auth_context,
)
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import AppSetting, AuthSession, LoginRateLimitBucket, User
from app.schemas.core import (
    ChangePasswordRequest,
    CsrfResponse,
    LoginRequest,
    LoginResponse,
    SetupRequest,
    SetupStatus,
    UserRead,
)
from app.security.auth import (
    hash_token,
    issue_preauth_csrf,
    issue_session_material,
)
from app.security.passwords import hash_password, needs_rehash, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])
GENERIC_LOGIN_ERROR = "The email or password is incorrect."


def _set_session_cookie(
    response: Response, settings: SettingsDep, raw_token: str, expires_at: datetime
) -> None:
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )


async def _create_auth_session(
    db: DbDep, settings: SettingsDep, user: User
) -> tuple[str, str, datetime]:
    raw_token, token_hash, csrf_token, csrf_hash, expires_at = issue_session_material(settings)
    now = datetime.now(UTC)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash,
            csrf_hash=csrf_hash,
            created_at=now,
            expires_at=expires_at,
            last_activity_at=now,
        )
    )
    return raw_token, csrf_token, expires_at


def _rate_key(settings: SettingsDep, email: str, source_ip: str) -> str:
    value = f"{email.lower().strip()}|{source_ip}".encode()
    return hmac.new(settings.app_secret_key.encode(), value, hashlib.sha256).hexdigest()


async def _check_and_record_login_attempt(
    db: DbDep,
    settings: SettingsDep,
    email: str,
    source_ip: str,
    *,
    succeeded: bool,
) -> None:
    now = datetime.now(UTC)
    key = _rate_key(settings, email, source_ip)
    bucket = (
        await db.execute(select(LoginRateLimitBucket).where(LoginRateLimitBucket.key_hash == key))
    ).scalar_one_or_none()
    if succeeded and bucket is None:
        return
    if bucket is None:
        bucket = LoginRateLimitBucket(
            key_hash=key,
            attempts=0,
            window_started_at=now,
        )
        db.add(bucket)
    blocked_until = bucket.blocked_until
    if blocked_until is not None and blocked_until.tzinfo is None:
        blocked_until = blocked_until.replace(tzinfo=UTC)
    if blocked_until is not None and blocked_until > now:
        raise ApiProblem(429, "login_rate_limited", "Too many login attempts. Try again later.")
    window_start = bucket.window_started_at
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=UTC)
    if now - window_start > timedelta(minutes=15):
        bucket.attempts = 0
        bucket.window_started_at = now
        bucket.blocked_until = None
    if succeeded:
        await db.delete(bucket)
        return
    bucket.attempts += 1
    if bucket.attempts >= 5:
        bucket.blocked_until = now + timedelta(minutes=15)


@router.get("/setup-status", response_model=SetupStatus)
async def setup_status(db: DbDep) -> SetupStatus:
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    return SetupStatus(setup_required=user_count == 0)


@router.get("/csrf", response_model=CsrfResponse)
async def csrf(
    response: Response,
    db: DbDep,
    settings: SettingsDep,
    context: Annotated[AuthContext | None, Depends(optional_auth_context)],
) -> CsrfResponse:
    if context is None:
        token = issue_preauth_csrf(settings)
        response.set_cookie(
            "authzdiff_preauth_csrf",
            token,
            max_age=600,
            httponly=False,
            secure=settings.session_cookie_secure,
            samesite="strict",
            path="/api/v1/auth",
        )
        return CsrfResponse(csrf_token=token)
    token = issue_preauth_csrf(settings)
    context.session.csrf_hash = hash_token(token)
    await db.commit()
    return CsrfResponse(csrf_token=token)


@router.post("/setup", response_model=LoginResponse, status_code=201)
async def setup(
    payload: SetupRequest,
    request: Request,
    response: Response,
    db: DbDep,
    settings: SettingsDep,
    _csrf: PreauthCsrfDep,
) -> LoginResponse:
    if not hmac.compare_digest(payload.setup_token, settings.first_admin_setup_token):
        raise ApiProblem(403, "setup_token_invalid", "The setup token is invalid.")
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    if user_count:
        raise ApiProblem(
            409,
            "setup_already_completed",
            "Initial setup has already been completed.",
        )
    password_hash = await to_thread.run_sync(hash_password, payload.password)
    user = User(
        email=str(payload.email).lower(),
        display_name=payload.display_name.strip(),
        password_hash=password_hash,
        role="administrator",
        is_active=True,
        must_change_password=False,
    )
    db.add(user)
    await db.flush()
    db.add(
        AppSetting(
            singleton_key="global",
            authorized_use_version="1.0",
            setup_completed=True,
            global_state_changes_enabled=settings.global_state_changes_enabled,
            updated_by=user.id,
        )
    )
    raw_token, csrf_token, expires_at = await _create_auth_session(db, settings, user)
    await record_audit(
        db,
        request,
        action="first_admin_setup",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        summary="First administrator completed authorized-use setup.",
    )
    await db.commit()
    await db.refresh(user)
    _set_session_cookie(response, settings, raw_token, expires_at)
    response.delete_cookie("authzdiff_preauth_csrf", path="/api/v1/auth")
    return LoginResponse(user=UserRead.model_validate(user), csrf_token=csrf_token)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbDep,
    settings: SettingsDep,
    _csrf: PreauthCsrfDep,
) -> LoginResponse:
    source_ip = request.client.host if request.client else "unknown"
    key = _rate_key(settings, str(payload.email), source_ip)
    existing_bucket = (
        await db.execute(select(LoginRateLimitBucket).where(LoginRateLimitBucket.key_hash == key))
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if existing_bucket and existing_bucket.blocked_until:
        blocked = existing_bucket.blocked_until
        if blocked.tzinfo is None:
            blocked = blocked.replace(tzinfo=UTC)
        if blocked > now:
            raise ApiProblem(429, "login_rate_limited", "Too many login attempts. Try again later.")
    user = (
        await db.execute(select(User).where(User.email == str(payload.email).lower()))
    ).scalar_one_or_none()
    verified = bool(
        user
        and user.is_active
        and await to_thread.run_sync(verify_password, user.password_hash, payload.password)
    )
    if not verified or user is None:
        await _check_and_record_login_attempt(
            db, settings, str(payload.email), source_ip, succeeded=False
        )
        await record_audit(
            db,
            request,
            action="login_failure",
            entity_type="authentication",
            outcome="denied",
            summary="Authentication failed.",
        )
        await db.commit()
        raise ApiProblem(401, "invalid_credentials", GENERIC_LOGIN_ERROR)
    await _check_and_record_login_attempt(
        db, settings, str(payload.email), source_ip, succeeded=True
    )
    if needs_rehash(user.password_hash):
        user.password_hash = await to_thread.run_sync(hash_password, payload.password)
    user.last_login_at = now
    raw_token, csrf_token, expires_at = await _create_auth_session(db, settings, user)
    await record_audit(
        db,
        request,
        action="login_success",
        entity_type="authentication",
        user_id=user.id,
        summary="User authenticated.",
    )
    await db.commit()
    await db.refresh(user)
    _set_session_cookie(response, settings, raw_token, expires_at)
    response.delete_cookie("authzdiff_preauth_csrf", path="/api/v1/auth")
    return LoginResponse(user=UserRead.model_validate(user), csrf_token=csrf_token)


@router.post("/logout", status_code=204, response_class=Response, response_model=None)
async def logout(
    request: Request,
    response: Response,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> Response:
    context.session.revoked_at = datetime.now(UTC)
    await record_audit(
        db,
        request,
        action="logout",
        entity_type="authentication",
        user_id=context.user.id,
        summary="User logged out.",
    )
    await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserRead)
async def me(
    context: Annotated[AuthContext, Depends(current_auth_context)],
) -> UserRead:
    return UserRead.model_validate(context.user)


@router.post("/change-password", response_model=LoginResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> LoginResponse:
    if not await to_thread.run_sync(
        verify_password, context.user.password_hash, payload.current_password
    ):
        raise ApiProblem(400, "current_password_invalid", "The current password is incorrect.")
    context.user.password_hash = await to_thread.run_sync(hash_password, payload.new_password)
    context.user.must_change_password = False
    await db.execute(
        delete(AuthSession).where(
            AuthSession.user_id == context.user.id,
            AuthSession.id != context.session.id,
        )
    )
    context.session.revoked_at = datetime.now(UTC)
    raw_token, csrf_token, expires_at = await _create_auth_session(db, settings, context.user)
    await record_audit(
        db,
        request,
        action="password_changed",
        entity_type="user",
        entity_id=context.user.id,
        user_id=context.user.id,
        summary="User changed their password and existing sessions were invalidated.",
    )
    await db.commit()
    await db.refresh(context.user)
    _set_session_cookie(response, settings, raw_token, expires_at)
    return LoginResponse(user=UserRead.model_validate(context.user), csrf_token=csrf_token)
