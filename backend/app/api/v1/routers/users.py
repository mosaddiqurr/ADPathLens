from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import DB, Administrator, AdministratorCsrf
from app.audit.service import record_audit
from app.core.errors import AppError
from app.core.security import hash_password
from app.models.entities import Role, User
from app.schemas.auth import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(db: DB, _: Administrator) -> list[User]:
    return list((await db.scalars(select(User).order_by(User.created_at))).all())


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(payload: UserCreate, request: Request, db: DB, administrator: AdministratorCsrf) -> User:
    email = str(payload.email).lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "Email already exists", "Choose another email.", code="duplicate_email")
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role.value,
    )
    db.add(user)
    await db.flush()
    await record_audit(
        db,
        request,
        "user.created",
        "user",
        f"Created {payload.role.value} user",
        user=administrator,
        entity_id=user.id,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    db: DB,
    administrator: AdministratorCsrf,
) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise AppError(404, "User not found", "The requested user does not exist.", code="not_found")
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.role is not None:
        if user.id == administrator.id and payload.role != Role.ADMINISTRATOR:
            raise AppError(409, "Cannot demote yourself", "Use another administrator.", code="self")
        user.role = payload.role.value
    if payload.is_active is not None:
        if user.id == administrator.id and not payload.is_active:
            raise AppError(409, "Cannot deactivate yourself", "Use another administrator.", code="self")
        user.is_active = payload.is_active
    await record_audit(db, request, "user.updated", "user", "User updated", user=administrator, entity_id=user.id)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(user_id: str, request: Request, db: DB, administrator: AdministratorCsrf) -> User:
    if user_id == administrator.id:
        raise AppError(409, "Cannot deactivate yourself", "Use another administrator.", code="self")
    user = await db.get(User, user_id)
    if not user:
        raise AppError(404, "User not found", "The requested user does not exist.", code="not_found")
    user.is_active = False
    await record_audit(
        db, request, "user.deactivated", "user", "User deactivated", user=administrator, entity_id=user.id
    )
    await db.commit()
    await db.refresh(user)
    return user
