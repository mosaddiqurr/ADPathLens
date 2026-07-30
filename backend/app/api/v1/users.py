from __future__ import annotations

from datetime import UTC, datetime

from anyio import to_thread
from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app.api.dependencies import AdminUserDep, CsrfContextDep, DbDep
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import User
from app.schemas.core import UserCreate, UserRead, UserUpdate
from app.security.passwords import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
async def list_users(db: DbDep, _admin: AdminUserDep) -> list[UserRead]:
    users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    return [UserRead.model_validate(user) for user in users]


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    payload: UserCreate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> UserRead:
    if context.user.role != "administrator":
        raise ApiProblem(403, "administrator_required", "Administrator access is required.")
    email = str(payload.email).lower()
    if (await db.execute(select(User.id).where(User.email == email))).scalar_one_or_none():
        raise ApiProblem(409, "email_in_use", "A user with this email already exists.")
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=await to_thread.run_sync(hash_password, payload.initial_password),
        role=payload.role,
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    await record_audit(
        db,
        request,
        action="user_created",
        entity_type="user",
        entity_id=user.id,
        user_id=context.user.id,
        summary=f"Created {payload.role} account.",
    )
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> UserRead:
    if context.user.role != "administrator":
        raise ApiProblem(403, "administrator_required", "Administrator access is required.")
    user = await db.get(User, user_id)
    if user is None:
        raise ApiProblem(404, "user_not_found", "The user was not found.")
    data = payload.model_dump(exclude_unset=True)
    if user.id == context.user.id and data.get("is_active") is False:
        raise ApiProblem(400, "cannot_deactivate_self", "You cannot deactivate your own account.")
    if data.get("role") == "analyst" and user.role == "administrator":
        admin_count = (
            await db.execute(
                select(func.count(User.id)).where(
                    User.role == "administrator", User.is_active.is_(True)
                )
            )
        ).scalar_one()
        if admin_count <= 1:
            raise ApiProblem(
                400, "last_administrator", "The last active administrator cannot be demoted."
            )
    for key, value in data.items():
        setattr(user, key, value)
    user.updated_at = datetime.now(UTC)
    await record_audit(
        db,
        request,
        action="user_updated",
        entity_type="user",
        entity_id=user.id,
        user_id=context.user.id,
        summary="Updated user account metadata.",
    )
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: str,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> UserRead:
    return await update_user(
        user_id,
        UserUpdate(is_active=False),
        request,
        db,
        context,
    )
