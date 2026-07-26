from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_session_token, secure_equals
from app.db.session import get_db
from app.models.entities import AuthSession, Role, User

DB = Annotated[AsyncSession, Depends(get_db)]


async def get_current_session(
    db: DB,
    raw_token: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> tuple[AuthSession, User]:
    if not raw_token:
        raise AppError(401, "Authentication required", "Please sign in to continue.", code="auth")
    query = (
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == hash_session_token(raw_token))
    )
    result = (await db.execute(query)).first()
    if not result:
        raise AppError(401, "Authentication required", "Your session is invalid.", code="auth")
    session, user = result
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if session.revoked_at or expires <= datetime.now(UTC) or not user.is_active:
        raise AppError(401, "Session expired", "Please sign in again.", code="session_expired")
    return session, user


async def get_current_user(
    session_and_user: Annotated[tuple[AuthSession, User], Depends(get_current_session)],
) -> User:
    return session_and_user[1]


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], Awaitable[User]]:
    async def role_dependency(user: CurrentUser) -> User:
        if user.role not in {role.value for role in roles}:
            raise AppError(
                403,
                "Insufficient permission",
                "Your role cannot perform this action.",
                code="forbidden",
            )
        return user

    return role_dependency


async def require_csrf(
    request: Request,
    session_and_user: Annotated[tuple[AuthSession, User], Depends(get_current_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> User:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        session, user = session_and_user
        if not csrf_token or not secure_equals(csrf_token, session.csrf_token):
            raise AppError(403, "CSRF validation failed", "Refresh and try again.", code="csrf")
        return user
    return session_and_user[1]


CsrfUser = Annotated[User, Depends(require_csrf)]
Administrator = Annotated[User, Depends(require_roles(Role.ADMINISTRATOR))]
Editor = Annotated[User, Depends(require_roles(Role.ADMINISTRATOR, Role.ANALYST))]


async def require_administrator_csrf(user: CsrfUser) -> User:
    if user.role != Role.ADMINISTRATOR.value:
        raise AppError(403, "Insufficient permission", "Administrator required.", code="forbidden")
    return user


async def require_editor_csrf(user: CsrfUser) -> User:
    if user.role not in {Role.ADMINISTRATOR.value, Role.ANALYST.value}:
        raise AppError(403, "Insufficient permission", "Administrator or analyst required.", code="forbidden")
    return user


AdministratorCsrf = Annotated[User, Depends(require_administrator_csrf)]
EditorCsrf = Annotated[User, Depends(require_editor_csrf)]
