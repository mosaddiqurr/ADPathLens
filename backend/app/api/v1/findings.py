from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from sqlalchemy import or_, select

from app.api.dependencies import CsrfContextDep, CurrentUserDep, DbDep
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import (
    ComparisonRun,
    Finding,
    FindingEvidence,
    FindingNote,
    FindingStatusHistory,
    ImportedRequest,
    Target,
    TestCase,
    User,
)
from app.schemas.findings import (
    FindingCreate,
    FindingEvidenceRead,
    FindingNoteCreate,
    FindingNoteRead,
    FindingRead,
    FindingStatusHistoryRead,
    FindingUpdate,
)
from app.services.authorization import project_for_user

router = APIRouter(tags=["findings"])


async def _finding_for_user(db: DbDep, user: User, finding_id: str) -> Finding:
    finding = await db.get(Finding, finding_id)
    if finding is None or finding.deleted_at is not None:
        raise ApiProblem(404, "finding_not_found", "The finding was not found.")
    await project_for_user(db, user, finding.project_id)
    return finding


@router.get("/projects/{project_id}/findings", response_model=list[FindingRead])
async def list_findings(
    project_id: str,
    db: DbDep,
    user: CurrentUserDep,
    search: str | None = None,
    severity: str | None = None,
    confidence: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    sort_by: str = "updated_at",
    sort_direction: str = "desc",
) -> list[FindingRead]:
    await project_for_user(db, user, project_id)
    statement = select(Finding).where(
        Finding.project_id == project_id, Finding.deleted_at.is_(None)
    )
    if search:
        pattern = f"%{search[:100]}%"
        statement = statement.where(
            or_(Finding.title.ilike(pattern), Finding.description.ilike(pattern))
        )
    if severity:
        statement = statement.where(Finding.severity == severity)
    if confidence:
        statement = statement.where(Finding.confidence == confidence)
    if priority:
        statement = statement.where(Finding.priority == priority)
    if status:
        statement = statement.where(Finding.status == status)
    sort_columns = {
        "updated_at": Finding.updated_at,
        "created_at": Finding.created_at,
        "severity": Finding.severity,
        "confidence": Finding.confidence,
        "priority": Finding.priority,
        "title": Finding.title,
        "status": Finding.status,
    }
    column = sort_columns.get(sort_by)
    if column is None or sort_direction not in {"asc", "desc"}:
        raise ApiProblem(422, "invalid_sort", "The requested finding sort is invalid.")
    ordering = column.asc() if sort_direction == "asc" else column.desc()
    rows = (await db.execute(statement.order_by(ordering, Finding.id).limit(500))).scalars().all()
    return [FindingRead.model_validate(row) for row in rows]


@router.get("/findings/{finding_id}", response_model=FindingRead)
async def get_finding(finding_id: str, db: DbDep, user: CurrentUserDep) -> FindingRead:
    return FindingRead.model_validate(await _finding_for_user(db, user, finding_id))


@router.post(
    "/projects/{project_id}/findings",
    response_model=FindingRead,
    status_code=201,
)
async def create_finding(
    project_id: str,
    payload: FindingCreate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> FindingRead:
    await project_for_user(db, context.user, project_id)
    run = await db.get(ComparisonRun, payload.comparison_run_id)
    test_case = await db.get(TestCase, run.test_case_id) if run else None
    request_definition = (
        await db.get(ImportedRequest, test_case.imported_request_id) if test_case else None
    )
    target = await db.get(Target, test_case.target_id) if test_case else None
    if (
        run is None
        or test_case is None
        or request_definition is None
        or target is None
        or test_case.project_id != project_id
    ):
        raise ApiProblem(404, "run_not_found", "The comparison run was not found.")
    finding = Finding(
        project_id=project_id,
        comparison_run_id=run.id,
        fingerprint=hashlib.sha256(
            f"manual:{project_id}:{run.id}:{payload.category}:{payload.title}".encode()
        ).hexdigest(),
        title=payload.title,
        category=payload.category,
        severity=payload.severity,
        confidence=payload.confidence,
        status="needs_review",
        target_snapshot=target.base_url,
        endpoint_snapshot=request_definition.path,
        expected_behaviour=test_case.expected_behaviour,
        observed_behaviour=run.explanation or "Manual review required.",
        description=payload.description,
        impact=payload.impact,
        reproduction_summary="Repeat the saved comparison against the authorized target.",
        remediation=payload.remediation,
        reviewer_notes="",
        priority=payload.priority,
        tags=sorted(set(payload.tags)),
        redaction_summary="Reusable authentication material was excluded.",
        limitations="Response comparison does not independently prove exploitability.",
        created_by=context.user.id,
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        recurrence_count=1,
    )
    db.add(finding)
    await db.flush()
    db.add(
        FindingStatusHistory(
            finding_id=finding.id,
            from_status=None,
            to_status="needs_review",
            changed_by=context.user.id,
            note="Finding created by reviewer.",
            created_at=datetime.now(UTC),
        )
    )
    await record_audit(
        db,
        request,
        action="finding_created",
        entity_type="finding",
        entity_id=finding.id,
        user_id=context.user.id,
        summary="Created a reviewer-controlled finding from sanitized evidence.",
    )
    await db.commit()
    await db.refresh(finding)
    return FindingRead.model_validate(finding)


@router.patch("/findings/{finding_id}", response_model=FindingRead)
async def update_finding(
    finding_id: str,
    payload: FindingUpdate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> FindingRead:
    finding = await _finding_for_user(db, context.user, finding_id)
    data = payload.model_dump(exclude_unset=True)
    status_note = data.pop("status_note", "")
    old_status = finding.status
    for key, value in data.items():
        if key == "tags" and value is not None:
            value = sorted(set(value))
        setattr(finding, key, value)
    if finding.status != old_status:
        db.add(
            FindingStatusHistory(
                finding_id=finding.id,
                from_status=old_status,
                to_status=finding.status,
                changed_by=context.user.id,
                note=status_note,
                created_at=datetime.now(UTC),
            )
        )
        if finding.status == "confirmed":
            finding.confirmed_by = context.user.id
            finding.confirmed_at = datetime.now(UTC)
    await record_audit(
        db,
        request,
        action="finding_updated",
        entity_type="finding",
        entity_id=finding.id,
        user_id=context.user.id,
        summary="Updated finding review metadata.",
    )
    await db.commit()
    await db.refresh(finding)
    return FindingRead.model_validate(finding)


@router.post(
    "/findings/{finding_id}/notes",
    response_model=FindingNoteRead,
    status_code=201,
)
async def add_finding_note(
    finding_id: str,
    payload: FindingNoteCreate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> FindingNoteRead:
    finding = await _finding_for_user(db, context.user, finding_id)
    note = FindingNote(
        finding_id=finding.id,
        author_id=context.user.id,
        body=payload.body,
    )
    db.add(note)
    await record_audit(
        db,
        request,
        action="finding_note_added",
        entity_type="finding",
        entity_id=finding.id,
        user_id=context.user.id,
        summary="Added a note to a finding.",
    )
    await db.commit()
    await db.refresh(note)
    return FindingNoteRead.model_validate(note)


@router.get("/findings/{finding_id}/notes", response_model=list[FindingNoteRead])
async def list_finding_notes(
    finding_id: str, db: DbDep, user: CurrentUserDep
) -> list[FindingNoteRead]:
    finding = await _finding_for_user(db, user, finding_id)
    rows = (
        (
            await db.execute(
                select(FindingNote)
                .where(FindingNote.finding_id == finding.id)
                .order_by(FindingNote.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [FindingNoteRead.model_validate(row) for row in rows]


@router.get(
    "/findings/{finding_id}/status-history",
    response_model=list[FindingStatusHistoryRead],
)
async def list_finding_status_history(
    finding_id: str,
    db: DbDep,
    user: CurrentUserDep,
) -> list[FindingStatusHistoryRead]:
    finding = await _finding_for_user(db, user, finding_id)
    rows = (
        (
            await db.execute(
                select(FindingStatusHistory)
                .where(FindingStatusHistory.finding_id == finding.id)
                .order_by(FindingStatusHistory.created_at, FindingStatusHistory.id)
            )
        )
        .scalars()
        .all()
    )
    return [FindingStatusHistoryRead.model_validate(row) for row in rows]


@router.get(
    "/findings/{finding_id}/evidence",
    response_model=list[FindingEvidenceRead],
)
async def list_finding_evidence(
    finding_id: str,
    db: DbDep,
    user: CurrentUserDep,
) -> list[FindingEvidenceRead]:
    finding = await _finding_for_user(db, user, finding_id)
    rows = (
        (
            await db.execute(
                select(FindingEvidence)
                .where(FindingEvidence.finding_id == finding.id)
                .order_by(FindingEvidence.created_at, FindingEvidence.id)
            )
        )
        .scalars()
        .all()
    )
    return [FindingEvidenceRead.model_validate(row) for row in rows]
