from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.problems import ApiProblem
from app.db.session import get_db
from app.models import AuthSession, User
from app.security.auth import hash_token, verify_preauth_csrf

DbDep = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: AuthSession


async def optional_auth_context(
    request: Request,
    db: DbDep,
    settings: SettingsDep,
) -> AuthContext | None:
    session_cookie = request.cookies.get(settings.session_cookie_name)
    if not session_cookie:
        return None
    token_hash = hash_token(session_cookie)
    row = await db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(
            AuthSession.token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
            User.is_active.is_(True),
        )
    )
    result = row.one_or_none()
    if result is None:
        return None
    session, user = result
    return AuthContext(user=user, session=session)


async def current_auth_context(
    context: Annotated[AuthContext | None, Depends(optional_auth_context)],
) -> AuthContext:
    if context is None:
        raise ApiProblem(401, "authentication_required", "Authentication is required.")
    return context


async def current_user(
    context: Annotated[AuthContext, Depends(current_auth_context)],
) -> User:
    if context.user.must_change_password:
        raise ApiProblem(
            403,
            "password_change_required",
            "The initial password must be replaced before continuing.",
        )
    return context.user


async def administrator(
    user: Annotated[User, Depends(current_user)],
) -> User:
    if user.role != "administrator":
        raise ApiProblem(403, "administrator_required", "Administrator access is required.")
    return user


async def require_authenticated_csrf(
    request: Request,
    context: Annotated[AuthContext, Depends(current_auth_context)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AuthContext:
    if not csrf_token or not secrets.compare_digest(
        hash_token(csrf_token), context.session.csrf_hash
    ):
        raise ApiProblem(403, "csrf_failed", "The CSRF token is missing or invalid.")
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        raise ApiProblem(403, "origin_rejected", "The request origin is not allowed.")
    if context.user.must_change_password and request.url.path not in {
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
    }:
        raise ApiProblem(
            403,
            "password_change_required",
            "The initial password must be replaced before continuing.",
        )
    return context


async def require_preauth_csrf(
    request: Request,
    settings: SettingsDep,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias="authzdiff_preauth_csrf")] = None,
) -> None:
    if (
        not csrf_header
        or not csrf_cookie
        or not secrets.compare_digest(csrf_header, csrf_cookie)
        or not verify_preauth_csrf(settings, csrf_header)
    ):
        raise ApiProblem(403, "csrf_failed", "The CSRF token is missing or invalid.")
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_origins:
        raise ApiProblem(403, "origin_rejected", "The request origin is not allowed.")


CurrentUserDep = Annotated[User, Depends(current_user)]
AdminUserDep = Annotated[User, Depends(administrator)]
CsrfContextDep = Annotated[AuthContext, Depends(require_authenticated_csrf)]
PreauthCsrfDep = Annotated[None, Depends(require_preauth_csrf)]
