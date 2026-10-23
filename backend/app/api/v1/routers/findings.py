import hashlib
import json
from collections import Counter
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import delete, func, or_, select

from app.api.deps import DB, CurrentUser, EditorCsrf
from app.audit.service import record_audit
from app.core.errors import AppError
from app.graph.service import build_graph
from app.models.entities import (
    AnalystNote,
    DirectoryNode,
    DirectoryRelationship,
    FindingNode,
    FindingPath,
    FindingRelationship,
    FindingStatusHistory,
    PathAnalysis,
    PrivilegePath,
    RiskFinding,
    RiskRuleConfiguration,
    User,
    utc_now,
)
from app.schemas.findings import (
    FindingCreate,
    FindingHistoryResponse,
    FindingResponse,
    FindingUpdate,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
    RiskSummaryResponse,
)
from app.schemas.graph import PageResponse
from app.scoring.engine import run_rules, score_detection
from app.services.authorization import project_or_404, snapshot_or_404

router = APIRouter(tags=["findings"])


def _finding_fingerprint(*parts: object) -> str:
    value = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _finding_or_404(db: DB, user: User, finding_id: str, minimum_role: str = "viewer") -> RiskFinding:
    finding = await db.get(RiskFinding, finding_id)
    if not finding:
        raise AppError(404, "Finding not found", "The finding does not exist.", code="not_found")
    await project_or_404(db, user, finding.project_id, minimum_role=minimum_role)
    return finding


@router.post("/snapshots/{snapshot_id}/risk-scan", response_model=RiskSummaryResponse)
async def risk_scan(snapshot_id: str, request: Request, db: DB, user: EditorCsrf) -> RiskSummaryResponse:
    snapshot = await snapshot_or_404(db, user, snapshot_id, minimum_role="analyst")
    graph = await build_graph(db, snapshot.id)
    await db.execute(
        delete(RiskFinding).where(
            RiskFinding.snapshot_id == snapshot.id,
            RiskFinding.rule_id.is_not(None),
            RiskFinding.status == "draft",
        )
    )
    configurations = list(
        (
            await db.scalars(
                select(RiskRuleConfiguration).order_by(
                    RiskRuleConfiguration.rule_id,
                    RiskRuleConfiguration.version.desc(),
                )
            )
        ).all()
    )
    latest_enabled: dict[str, bool] = {}
    for configuration in configurations:
        latest_enabled.setdefault(configuration.rule_id, configuration.enabled)
    detections = [detection for detection in run_rules(graph) if latest_enabled.get(detection.rule_id, True)]
    for detection in detections:
        score, severity = score_detection(detection)
        node = await db.get(DirectoryNode, detection.node_id) if detection.node_id else None
        relationship = (
            await db.get(DirectoryRelationship, detection.relationship_id) if detection.relationship_id else None
        )
        fingerprint = _finding_fingerprint(
            detection.rule_id,
            node.external_id if node else None,
            relationship.external_id if relationship else None,
            detection.category,
        )
        previous = await db.scalar(
            select(RiskFinding)
            .where(
                RiskFinding.project_id == snapshot.project_id,
                RiskFinding.stable_fingerprint == fingerprint,
                RiskFinding.snapshot_id != snapshot.id,
            )
            .order_by(RiskFinding.last_seen_at.desc())
            .limit(1)
        )
        observed_at = utc_now()
        finding = RiskFinding(
            project_id=snapshot.project_id,
            snapshot_id=snapshot.id,
            node_id=detection.node_id,
            relationship_id=detection.relationship_id,
            rule_id=detection.rule_id,
            rule_version="1.0",
            title=detection.title,
            category=detection.category,
            severity=severity,
            confidence=detection.confidence,
            internal_score=score,
            priority="high" if severity in {"high", "critical"} else "medium",
            status="draft",
            description=detection.description,
            technical_explanation=detection.impact,
            impact=detection.impact,
            evidence=detection.evidence or {},
            contributing_signals=list(detection.signals),
            reducing_signals=list(detection.reducing),
            remediation=detection.remediation,
            validation_steps=[
                "Validate the imported relationship against an authorised source.",
                "Confirm the affected principal and target are still active.",
                "Retest the path after the proposed defensive change.",
            ],
            limitations=(
                "This finding is derived from imported relationships and requires human review. "
                "It does not prove compromise or exploitability."
            ),
            stable_fingerprint=fingerprint,
            first_seen_at=previous.first_seen_at if previous else observed_at,
            last_seen_at=observed_at,
            recurrence_count=(previous.recurrence_count + 1) if previous else 1,
            created_by=user.id,
        )
        db.add(finding)
        await db.flush()
        if detection.node_id:
            db.add(FindingNode(finding_id=finding.id, node_id=detection.node_id))
        if detection.relationship_id:
            db.add(
                FindingRelationship(
                    finding_id=finding.id,
                    relationship_id=detection.relationship_id,
                )
            )
        db.add(
            FindingStatusHistory(
                finding_id=finding.id,
                previous_status=None,
                new_status="draft",
                note="Created by deterministic risk scan.",
                changed_by=user.id,
            )
        )
    await record_audit(
        db,
        request,
        "risk.scan_completed",
        "snapshot",
        f"Risk scan created {len(detections)} draft finding(s)",
        user=user,
        entity_id=snapshot.id,
        project_id=snapshot.project_id,
    )
    await db.commit()
    return await risk_summary(snapshot.id, db, user)


@router.get("/snapshots/{snapshot_id}/risk-summary", response_model=RiskSummaryResponse)
async def risk_summary(snapshot_id: str, db: DB, user: CurrentUser) -> RiskSummaryResponse:
    await snapshot_or_404(db, user, snapshot_id)
    findings = list((await db.scalars(select(RiskFinding).where(RiskFinding.snapshot_id == snapshot_id))).all())
    return RiskSummaryResponse(
        snapshot_id=snapshot_id,
        total=len(findings),
        by_severity=dict(sorted(Counter(item.severity for item in findings).items())),
        by_status=dict(sorted(Counter(item.status for item in findings).items())),
        by_category=dict(sorted(Counter(item.category for item in findings).items())),
    )


@router.get("/projects/{project_id}/findings", response_model=PageResponse)
async def list_findings(
    project_id: str,
    db: DB,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    search: str = "",
    severity: str = "",
    confidence: str = "",
    status: str = "",
    sort: str = "-created_at",
    snapshot_id: str = "",
) -> PageResponse:
    await project_or_404(db, user, project_id)
    conditions = [RiskFinding.project_id == project_id]
    if snapshot_id:
        conditions.append(RiskFinding.snapshot_id == snapshot_id)
    if search:
        term = f"%{search[:256]}%"
        conditions.append(or_(RiskFinding.title.ilike(term), RiskFinding.description.ilike(term)))
    if severity:
        conditions.append(RiskFinding.severity == severity)
    if confidence:
        conditions.append(RiskFinding.confidence == confidence)
    if status:
        conditions.append(RiskFinding.status == status)
    sort_columns: dict[str, Any] = {
        "created_at": RiskFinding.created_at.asc(),
        "-created_at": RiskFinding.created_at.desc(),
        "severity": RiskFinding.severity.asc(),
        "-severity": RiskFinding.severity.desc(),
        "title": RiskFinding.title.asc(),
        "-title": RiskFinding.title.desc(),
    }
    if sort not in sort_columns:
        raise AppError(422, "Invalid sort", "Choose a documented sort field.", code="sort")
    total = await db.scalar(select(func.count(RiskFinding.id)).where(*conditions)) or 0
    findings = list(
        (
            await db.scalars(
                select(RiskFinding)
                .where(*conditions)
                .order_by(sort_columns[sort], RiskFinding.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return PageResponse(
        items=[FindingResponse.model_validate(finding).model_dump() for finding in findings],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/projects/{project_id}/findings", response_model=FindingResponse, status_code=201)
async def create_finding(
    project_id: str,
    payload: FindingCreate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> RiskFinding:
    await project_or_404(db, user, project_id, minimum_role="analyst")
    snapshot = await snapshot_or_404(db, user, payload.snapshot_id, minimum_role="analyst")
    if snapshot.project_id != project_id:
        raise AppError(422, "Snapshot mismatch", "Use a snapshot from this project.", code="scope")
    if payload.node_id:
        node = await db.get(DirectoryNode, payload.node_id)
        if not node or node.snapshot_id != snapshot.id:
            raise AppError(
                422,
                "Invalid node",
                "Select a node from the finding snapshot.",
                code="node",
            )
    if payload.relationship_id:
        relationship = await db.get(DirectoryRelationship, payload.relationship_id)
        if not relationship or relationship.snapshot_id != snapshot.id:
            raise AppError(
                422,
                "Invalid relationship",
                "Select a relationship from the finding snapshot.",
                code="relationship",
            )
    if payload.privilege_path_id:
        path = await db.get(PrivilegePath, payload.privilege_path_id)
        analysis = await db.get(PathAnalysis, path.path_analysis_id) if path else None
        if not path or not analysis or analysis.snapshot_id != snapshot.id:
            raise AppError(
                422,
                "Invalid path",
                "Select a path from the finding snapshot.",
                code="path",
            )
    finding = RiskFinding(
        project_id=project_id,
        snapshot_id=snapshot.id,
        node_id=payload.node_id,
        relationship_id=payload.relationship_id,
        privilege_path_id=payload.privilege_path_id,
        title=payload.title,
        category=payload.category,
        severity=payload.severity,
        confidence=payload.confidence,
        internal_score={
            "informational": 10,
            "low": 30,
            "medium": 50,
            "high": 75,
            "critical": 90,
        }[payload.severity],
        status="open",
        stable_fingerprint=_finding_fingerprint(
            "manual",
            payload.category,
            payload.title.strip().casefold(),
            payload.node_id,
            payload.relationship_id,
            payload.privilege_path_id,
        ),
        first_seen_at=utc_now(),
        last_seen_at=utc_now(),
        recurrence_count=1,
        description=payload.description,
        technical_explanation=payload.technical_explanation,
        impact=payload.impact,
        remediation=payload.remediation,
        validation_steps=payload.validation_steps,
        limitations=payload.limitations,
        created_by=user.id,
    )
    db.add(finding)
    await db.flush()
    if payload.node_id:
        db.add(FindingNode(finding_id=finding.id, node_id=payload.node_id))
    if payload.relationship_id:
        db.add(
            FindingRelationship(
                finding_id=finding.id,
                relationship_id=payload.relationship_id,
            )
        )
    if payload.privilege_path_id:
        db.add(
            FindingPath(
                finding_id=finding.id,
                path_id=payload.privilege_path_id,
            )
        )
    db.add(
        FindingStatusHistory(
            finding_id=finding.id,
            previous_status=None,
            new_status="open",
            note="Manually created by analyst.",
            changed_by=user.id,
        )
    )
    await record_audit(
        db,
        request,
        "finding.created",
        "finding",
        "Manual finding created",
        user=user,
        entity_id=finding.id,
        project_id=finding.project_id,
    )
    await db.commit()
    await db.refresh(finding)
    return finding


@router.get("/findings/{finding_id}", response_model=FindingResponse)
async def get_finding(finding_id: str, db: DB, user: CurrentUser) -> RiskFinding:
    return await _finding_or_404(db, user, finding_id)


@router.get("/findings/{finding_id}/evidence", response_model=dict[str, object])
async def get_finding_evidence(finding_id: str, db: DB, user: CurrentUser) -> dict[str, object]:
    finding = await _finding_or_404(db, user, finding_id)
    node_ids = list((await db.scalars(select(FindingNode.node_id).where(FindingNode.finding_id == finding.id))).all())
    relationship_ids = list(
        (
            await db.scalars(
                select(FindingRelationship.relationship_id).where(FindingRelationship.finding_id == finding.id)
            )
        ).all()
    )
    path_ids = list((await db.scalars(select(FindingPath.path_id).where(FindingPath.finding_id == finding.id))).all())
    return {
        "finding_id": finding.id,
        "snapshot_id": finding.snapshot_id,
        "node_ids": node_ids,
        "relationship_ids": relationship_ids,
        "path_ids": path_ids,
        "evidence": finding.evidence,
        "limitations": finding.limitations,
    }


@router.patch("/findings/{finding_id}", response_model=FindingResponse)
async def update_finding(
    finding_id: str,
    payload: FindingUpdate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> RiskFinding:
    finding = await _finding_or_404(db, user, finding_id, minimum_role="analyst")
    previous_status = finding.status
    changes = payload.model_dump(exclude_unset=True, exclude={"status_note"})
    for key, value in changes.items():
        setattr(finding, key, value)
    if payload.status is not None and payload.status != previous_status:
        finding.reviewed_by = user.id
        finding.reviewed_at = utc_now()
        db.add(
            FindingStatusHistory(
                finding_id=finding.id,
                previous_status=previous_status,
                new_status=payload.status,
                note=payload.status_note,
                changed_by=user.id,
            )
        )
    finding.record_version += 1
    await record_audit(
        db,
        request,
        "finding.updated",
        "finding",
        "Finding review updated",
        user=user,
        entity_id=finding.id,
        project_id=finding.project_id,
        context={"previous_status": previous_status, "status": finding.status},
    )
    await db.commit()
    await db.refresh(finding)
    return finding


@router.get(
    "/findings/{finding_id}/history",
    response_model=list[FindingHistoryResponse],
)
async def finding_history(finding_id: str, db: DB, user: CurrentUser) -> list[FindingStatusHistory]:
    finding = await _finding_or_404(db, user, finding_id)
    return list(
        (
            await db.scalars(
                select(FindingStatusHistory)
                .where(FindingStatusHistory.finding_id == finding.id)
                .order_by(FindingStatusHistory.changed_at, FindingStatusHistory.id)
            )
        ).all()
    )


@router.get("/findings/{finding_id}/notes", response_model=list[NoteResponse])
async def list_finding_notes(finding_id: str, db: DB, user: CurrentUser) -> list[AnalystNote]:
    finding = await _finding_or_404(db, user, finding_id)
    return list(
        (
            await db.scalars(
                select(AnalystNote)
                .where(
                    AnalystNote.project_id == finding.project_id,
                    AnalystNote.entity_type == "finding",
                    AnalystNote.entity_id == finding.id,
                )
                .order_by(AnalystNote.created_at)
            )
        ).all()
    )


@router.post("/findings/{finding_id}/notes", response_model=NoteResponse, status_code=201)
async def add_finding_note(
    finding_id: str,
    payload: NoteCreate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> AnalystNote:
    finding = await _finding_or_404(db, user, finding_id, minimum_role="analyst")
    note = AnalystNote(
        project_id=finding.project_id,
        entity_type="finding",
        entity_id=finding.id,
        body=payload.body,
        created_by=user.id,
    )
    db.add(note)
    await record_audit(
        db,
        request,
        "finding.note_added",
        "finding",
        "Analyst note added",
        user=user,
        entity_id=finding.id,
        project_id=finding.project_id,
    )
    await db.commit()
    await db.refresh(note)
    return note


@router.patch("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    payload: NoteUpdate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> AnalystNote:
    note = await db.get(AnalystNote, note_id)
    if not note:
        raise AppError(404, "Note not found", "The note does not exist.", code="not_found")
    await project_or_404(db, user, note.project_id, minimum_role="analyst")
    note.body = payload.body
    await record_audit(
        db,
        request,
        "note.updated",
        "note",
        "Analyst note updated",
        user=user,
        entity_id=note.id,
        project_id=note.project_id,
    )
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: str, request: Request, db: DB, user: EditorCsrf) -> None:
    note = await db.get(AnalystNote, note_id)
    if not note:
        raise AppError(404, "Note not found", "The note does not exist.", code="not_found")
    await project_or_404(db, user, note.project_id, minimum_role="analyst")
    await record_audit(
        db,
        request,
        "note.deleted",
        "note",
        "Analyst note deleted",
        user=user,
        entity_id=note.id,
        project_id=note.project_id,
    )
    await db.delete(note)
    await db.commit()
