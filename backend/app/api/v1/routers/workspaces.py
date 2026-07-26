from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import DB, CsrfUser, CurrentUser
from app.audit.service import record_audit
from app.core.errors import AppError
from app.models.entities import User, Workspace, WorkspaceMembership
from app.schemas.workspaces import (
    MembershipCreate,
    MembershipResponse,
    MembershipUpdate,
    WorkspaceCreate,
    WorkspaceResponse,
)
from app.services.authorization import workspace_or_404

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(db: DB, user: CurrentUser) -> list[Workspace]:
    query = (
        select(Workspace)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(Workspace.updated_at.desc())
    )
    return list((await db.scalars(query)).all())


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(payload: WorkspaceCreate, request: Request, db: DB, user: CsrfUser) -> Workspace:
    if user.role == "viewer":
        raise AppError(403, "Insufficient permission", "Viewers cannot create workspaces.", code="forbidden")
    workspace = Workspace(
        name=payload.name.strip(),
        description=payload.description.strip(),
        created_by=user.id,
    )
    db.add(workspace)
    await db.flush()
    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role="administrator",
            created_by=user.id,
        )
    )
    await record_audit(
        db,
        request,
        "workspace.created",
        "workspace",
        "Workspace created",
        user=user,
        entity_id=workspace.id,
    )
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, db: DB, user: CurrentUser) -> Workspace:
    return await workspace_or_404(db, user, workspace_id)


@router.get("/{workspace_id}/members", response_model=list[MembershipResponse])
async def list_members(workspace_id: str, db: DB, user: CurrentUser) -> list[WorkspaceMembership]:
    await workspace_or_404(db, user, workspace_id)
    return list(
        (
            await db.scalars(
                select(WorkspaceMembership)
                .where(WorkspaceMembership.workspace_id == workspace_id)
                .order_by(WorkspaceMembership.created_at)
            )
        ).all()
    )


@router.post("/{workspace_id}/members", response_model=MembershipResponse, status_code=201)
async def add_member(
    workspace_id: str,
    payload: MembershipCreate,
    request: Request,
    db: DB,
    user: CsrfUser,
) -> WorkspaceMembership:
    await workspace_or_404(db, user, workspace_id, minimum_role="administrator")
    member = await db.get(User, payload.user_id)
    if not member or not member.is_active:
        raise AppError(404, "User not found", "The active user does not exist.", code="not_found")
    existing = await db.scalar(
        select(WorkspaceMembership.id).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == payload.user_id,
        )
    )
    if existing:
        raise AppError(409, "Already a member", "Update the existing membership.", code="duplicate")
    membership = WorkspaceMembership(
        workspace_id=workspace_id,
        user_id=payload.user_id,
        role=payload.role,
        created_by=user.id,
    )
    db.add(membership)
    await db.flush()
    await record_audit(
        db,
        request,
        "workspace.member_added",
        "workspace",
        "Workspace member added",
        user=user,
        entity_id=workspace_id,
        context={"member_id": payload.user_id, "role": payload.role},
    )
    await db.commit()
    await db.refresh(membership)
    return membership


@router.patch("/{workspace_id}/members/{membership_id}", response_model=MembershipResponse)
async def update_member(
    workspace_id: str,
    membership_id: str,
    payload: MembershipUpdate,
    request: Request,
    db: DB,
    user: CsrfUser,
) -> WorkspaceMembership:
    await workspace_or_404(db, user, workspace_id, minimum_role="administrator")
    membership = await db.get(WorkspaceMembership, membership_id)
    if not membership or membership.workspace_id != workspace_id:
        raise AppError(404, "Membership not found", "The membership does not exist.", code="not_found")
    if membership.user_id == user.id and payload.role != "administrator":
        raise AppError(409, "Cannot demote yourself", "Use another workspace administrator.", code="self")
    membership.role = payload.role
    await record_audit(
        db,
        request,
        "workspace.member_updated",
        "workspace",
        "Workspace membership updated",
        user=user,
        entity_id=workspace_id,
        context={"member_id": membership.user_id, "role": payload.role},
    )
    await db.commit()
    await db.refresh(membership)
    return membership


@router.delete("/{workspace_id}/members/{membership_id}", status_code=204)
async def remove_member(
    workspace_id: str,
    membership_id: str,
    request: Request,
    db: DB,
    user: CsrfUser,
) -> None:
    await workspace_or_404(db, user, workspace_id, minimum_role="administrator")
    membership = await db.get(WorkspaceMembership, membership_id)
    if not membership or membership.workspace_id != workspace_id:
        raise AppError(404, "Membership not found", "The membership does not exist.", code="not_found")
    if membership.user_id == user.id:
        raise AppError(409, "Cannot remove yourself", "Use another workspace administrator.", code="self")
    await db.delete(membership)
    await record_audit(
        db,
        request,
        "workspace.member_removed",
        "workspace",
        "Workspace member removed",
        user=user,
        entity_id=workspace_id,
        context={"member_id": membership.user_id},
    )
    await db.commit()
