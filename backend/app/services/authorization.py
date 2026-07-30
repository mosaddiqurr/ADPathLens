from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.problems import ApiProblem
from app.models import Project, Target, User


async def project_for_user(
    db: AsyncSession,
    user: User,
    project_id: str,
    *,
    include_deleted: bool = False,
) -> Project:
    project = await db.get(Project, project_id)
    if (
        project is None
        or (project.deleted_at is not None and not include_deleted)
        or (user.role != "administrator" and project.created_by != user.id)
    ):
        # Deliberately indistinguishable to prevent cross-user resource discovery.
        raise ApiProblem(404, "project_not_found", "The project was not found.")
    return project


async def target_for_user(
    db: AsyncSession,
    user: User,
    target_id: str,
) -> Target:
    target = await db.get(Target, target_id)
    if target is None:
        raise ApiProblem(404, "target_not_found", "The target was not found.")
    await project_for_user(db, user, target.project_id)
    return target
