from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.entities import Dataset, GraphSnapshot, Project, User, Workspace, WorkspaceMembership

ROLE_LEVEL = {"viewer": 1, "analyst": 2, "administrator": 3}


async def workspace_membership(
    db: AsyncSession,
    user: User,
    workspace_id: str,
    *,
    minimum_role: str = "viewer",
) -> WorkspaceMembership:
    membership = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if not membership:
        raise AppError(404, "Workspace not found", "The workspace does not exist.", code="not_found")
    if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum_role]:
        raise AppError(
            403,
            "Insufficient workspace permission",
            f"This action requires the {minimum_role} workspace role.",
            code="forbidden",
        )
    return membership


async def workspace_or_404(
    db: AsyncSession,
    user: User,
    workspace_id: str,
    *,
    minimum_role: str = "viewer",
) -> Workspace:
    await workspace_membership(db, user, workspace_id, minimum_role=minimum_role)
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise AppError(404, "Workspace not found", "The workspace does not exist.", code="not_found")
    return workspace


async def project_or_404(
    db: AsyncSession,
    user: User,
    project_id: str,
    *,
    minimum_role: str = "viewer",
) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise AppError(404, "Project not found", "The project does not exist.", code="not_found")
    await workspace_membership(db, user, project.workspace_id, minimum_role=minimum_role)
    return project


async def dataset_or_404(
    db: AsyncSession,
    user: User,
    dataset_id: str,
    *,
    minimum_role: str = "viewer",
) -> Dataset:
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise AppError(404, "Dataset not found", "The import does not exist.", code="not_found")
    await project_or_404(db, user, dataset.project_id, minimum_role=minimum_role)
    return dataset


async def snapshot_or_404(
    db: AsyncSession,
    user: User,
    snapshot_id: str,
    *,
    minimum_role: str = "viewer",
) -> GraphSnapshot:
    snapshot = await db.get(GraphSnapshot, snapshot_id)
    if not snapshot:
        raise AppError(404, "Snapshot not found", "The snapshot does not exist.", code="not_found")
    await project_or_404(db, user, snapshot.project_id, minimum_role=minimum_role)
    return snapshot
