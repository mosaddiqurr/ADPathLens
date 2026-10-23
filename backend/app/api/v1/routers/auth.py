from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from secrets import token_urlsafe
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, CsrfUser, get_current_session
from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    hash_password,
    new_session_credentials,
    session_expiry,
    verify_password,
)
from app.models.entities import (
    ApplicationSetting,
    AuthSession,
    Role,
    User,
    Workspace,
    WorkspaceMembership,
    utc_now,
)
from app.schemas.auth import AuthResponse, LoginRequest, SetupRequest, SetupStatus, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])
attempts: defaultdict[str, deque[datetime]] = defaultdict(deque)


def _check_rate_limit(key: str) -> None:
    now = datetime.now(UTC)
    window = now - timedelta(minutes=15)
    bucket = attempts[key]
    while bucket and bucket[0] < window:
        bucket.popleft()
    if len(bucket) >= 10:
        raise AppError(429, "Too many attempts", "Try again later.", code="rate_limited")
    bucket.append(now)


def _set_session_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=settings.session_expiry_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _local_request_allowed(request: Request) -> bool:
    settings = get_settings()
    if not settings.local_mode or settings.app_env != "development" or not request.client:
        return False
    try:
        if not ip_address(request.client.host).is_loopback:
            return False
    except ValueError:
        return False
    if request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return False
    origin = request.headers.get("origin")
    if origin:
        if origin not in settings.cors_origins or urlparse(origin).hostname not in {"localhost", "127.0.0.1", "::1"}:
            return False
    return request.headers.get("sec-fetch-site") != "cross-site"


@router.get("/local-status")
async def local_status(request: Request) -> dict[str, bool]:
    return {"available": _local_request_allowed(request)}


@router.post("/local-session", response_model=AuthResponse)
async def local_session(request: Request, response: Response, db: DB) -> AuthResponse:
    """Open the dedicated local analyst without bypassing session or object protections."""
    if not _local_request_allowed(request) or request.headers.get("X-ADPathLens-Local") != "1":
        raise AppError(
            403, "Local access unavailable", "Local access requires the loopback development server.", code="local"
        )
    email = "local@adpathlens.invalid"
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        if await db.scalar(select(func.count(User.id))):
            raise AppError(
                409,
                "Existing accounts found",
                "Use a separate empty database for local mode, or set LOCAL_MODE=false and sign in.",
                code="local_database",
            )
        user = User(
            email=email,
            display_name="Local analyst",
            password_hash=hash_password(token_urlsafe(48)),
            role=Role.ANALYST.value,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        workspace = Workspace(name="Local directory analysis", description="Local portfolio data", created_by=user.id)
        db.add(workspace)
        await db.flush()
        db.add(
            WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role=Role.ANALYST.value, created_by=user.id)
        )
    if not user.is_active or user.role != Role.ANALYST.value:
        raise AppError(403, "Local access unavailable", "The local analyst is unavailable.", code="local")
    raw, token_hash, csrf = new_session_credentials()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash,
            csrf_token=csrf,
            expires_at=session_expiry(),
            created_ip=request.client.host if request.client else None,
        )
    )
    await record_audit(db, request, "auth.local_session", "user", "Local analyst session opened", user=user)
    await db.commit()
    await db.refresh(user)
    _set_session_cookie(response, raw)
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf)


@router.get("/setup-status", response_model=SetupStatus)
async def setup_status(db: DB) -> SetupStatus:
    count = await db.scalar(select(func.count(User.id)))
    return SetupStatus(setup_required=count == 0)


@router.post("/setup", response_model=AuthResponse, status_code=201)
async def setup(payload: SetupRequest, request: Request, response: Response, db: DB) -> AuthResponse:
    if not payload.authorization_confirmed:
        raise AppError(
            422,
            "Authorization confirmation required",
            "Confirm the authorized-use statement before setup.",
            code="authorization_required",
        )
    if await db.scalar(select(func.count(User.id))) != 0:
        raise AppError(409, "Setup complete", "The first administrator already exists.", code="setup")
    user = User(
        email=str(payload.email).strip().lower(),
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=Role.ADMINISTRATOR.value,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    workspace = Workspace(
        name="ADPathLens Workspace",
        description="Default workspace created during first-administrator setup.",
        created_by=user.id,
    )
    db.add(workspace)
    await db.flush()
    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=Role.ADMINISTRATOR.value,
            created_by=user.id,
        )
    )
    db.add(
        ApplicationSetting(
            key="system.setup_complete",
            value_json={"value": True},
            changed_by=user.id,
        )
    )
    raw, token_hash, csrf = new_session_credentials()
    session = AuthSession(
        user_id=user.id,
        token_hash=token_hash,
        csrf_token=csrf,
        expires_at=session_expiry(),
        created_ip=request.client.host if request.client else None,
    )
    db.add(session)
    await record_audit(db, request, "user.created", "user", "First administrator created", user=user, entity_id=user.id)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(409, "Setup complete", "The first administrator already exists.", code="setup") from exc
    await db.refresh(user)
    _set_session_cookie(response, raw)
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: DB) -> AuthResponse:
    email = str(payload.email).strip().lower()
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(f"{ip}:{email}")
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(user.password_hash, payload.password):
        await record_audit(db, request, "auth.login_failed", "user", "Login failed", outcome="failure")
        await db.commit()
        raise AppError(401, "Sign-in failed", "Email or password is incorrect.", code="login_failed")
    raw, token_hash, csrf = new_session_credentials()
    session = AuthSession(
        user_id=user.id,
        token_hash=token_hash,
        csrf_token=csrf,
        expires_at=session_expiry(),
        created_ip=ip,
    )
    user.last_login_at = utc_now()
    db.add(session)
    await record_audit(db, request, "auth.login_success", "user", "Login succeeded", user=user)
    await db.commit()
    await db.refresh(user)
    attempts.pop(f"{ip}:{email}", None)
    _set_session_cookie(response, raw)
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: DB,
    user: CsrfUser,
    session_and_user: tuple[AuthSession, User] = Depends(get_current_session),
) -> None:
    session, _ = session_and_user
    session.revoked_at = utc_now()
    await record_audit(db, request, "auth.logout", "user", "Logout", user=user)
    await db.commit()
    settings = get_settings()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


@router.get("/me", response_model=UserResponse)
async def me(user: CsrfUser) -> User:
    return user


@router.get("/csrf")
async def csrf_token(
    session_and_user: tuple[AuthSession, User] = Depends(get_current_session),
) -> dict[str, str]:
    session, _ = session_and_user
    return {"csrf_token": session.csrf_token}


@router.post("/logout-all", status_code=204)
async def logout_all(request: Request, db: DB, user: CsrfUser) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    await record_audit(db, request, "auth.logout_all", "user", "All sessions revoked", user=user)
    await db.commit()
