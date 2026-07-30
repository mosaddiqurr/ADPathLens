from __future__ import annotations

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.api.dependencies import CsrfContextDep, CurrentUserDep, DbDep
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import Project, ProjectPolicy
from app.schemas.core import DeleteConfirmation, ProjectCreate, ProjectRead, ProjectUpdate
from app.services.authorization import project_for_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(db: DbDep, _user: CurrentUserDep) -> list[ProjectRead]:
    ownership_filter = (
        Project.deleted_at.is_(None)
        if _user.role == "administrator"
        else (Project.deleted_at.is_(None) & (Project.created_by == _user.id))
    )
    projects = (
        (
            await db.execute(
                select(Project).where(ownership_filter).order_by(Project.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [ProjectRead.model_validate(project) for project in projects]


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> ProjectRead:
    project = Project(
        name=payload.name.strip(),
        description=payload.description,
        status="active",
        created_by=context.user.id,
    )
    db.add(project)
    await db.flush()
    db.add(ProjectPolicy(project_id=project.id))
    await record_audit(
        db,
        request,
        action="project_created",
        entity_type="project",
        entity_id=project.id,
        user_id=context.user.id,
        summary="Created a testing project.",
    )
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: str, db: DbDep, _user: CurrentUserDep) -> ProjectRead:
    return ProjectRead.model_validate(await project_for_user(db, _user, project_id))


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> ProjectRead:
    project = await project_for_user(db, context.user, project_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    await record_audit(
        db,
        request,
        action="project_updated",
        entity_type="project",
        entity_id=project.id,
        user_id=context.user.id,
        summary="Updated project metadata.",
    )
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def delete_project(
    project_id: str,
    payload: DeleteConfirmation,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> None:
    project = await project_for_user(db, context.user, project_id)
    if payload.confirmation != project.name:
        raise ApiProblem(
            400, "confirmation_mismatch", "Type the exact project name to confirm deletion."
        )
    # Keep the row as an audit tombstone while excluding it from all normal queries.
    from datetime import UTC, datetime

    project.deleted_at = datetime.now(UTC)
    project.status = "archived"
    await record_audit(
        db,
        request,
        action="project_deleted",
        entity_type="project",
        entity_id=project.id,
        user_id=context.user.id,
        summary="Deleted a project after exact-name confirmation.",
    )
    await db.commit()
