from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from sqlalchemy import case, func, select

from app.api.deps import DB, CurrentUser, EditorCsrf
from app.api.v1.routers.analysis import _analysis_response
from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.entities import (
    Dataset,
    DirectoryNode,
    DirectoryRelationship,
    PathAnalysis,
    PrivilegePath,
    RemediationPlan,
    Report,
    RiskFinding,
    SnapshotComparison,
    User,
)
from app.reporting.service import generate_report
from app.schemas.reports import ReportCreate, ReportResponse
from app.scoring.path_priority import path_severity
from app.services.authorization import project_or_404, snapshot_or_404

router = APIRouter(tags=["reports"])
settings = get_settings()


async def _report_or_404(db: DB, user: User, report_id: str) -> Report:
    report = await db.get(Report, report_id)
    if not report:
        raise AppError(404, "Report not found", "The report does not exist.", code="not_found")
    await project_or_404(db, user, report.project_id)
    return report


def _finding_dict(finding: RiskFinding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "rule_id": finding.rule_id,
        "rule_version": finding.rule_version,
        "title": finding.title,
        "category": finding.category,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "score": finding.internal_score,
        "priority": finding.priority,
        "status": finding.status,
        "description": finding.description,
        "technical_explanation": finding.technical_explanation,
        "impact": finding.impact,
        "evidence": finding.evidence,
        "contributing_signals": finding.contributing_signals,
        "reducing_signals": finding.reducing_signals,
        "remediation": finding.remediation,
        "validation_steps": finding.validation_steps,
        "limitations": finding.limitations,
    }


def _available_report_path(storage_path: str) -> Path | None:
    path = Path(storage_path).resolve()
    root = settings.report_storage_path.resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


@router.get("/projects/{project_id}/reports", response_model=list[ReportResponse])
async def list_reports(project_id: str, db: DB, user: CurrentUser) -> list[Report]:
    await project_or_404(db, user, project_id)
    return list(
        (
            await db.scalars(select(Report).where(Report.project_id == project_id).order_by(Report.generated_at.desc()))
        ).all()
    )


@router.post(
    "/projects/{project_id}/reports",
    response_model=ReportResponse,
    status_code=201,
)
async def create_report(
    project_id: str,
    payload: ReportCreate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> Report:
    project = await project_or_404(db, user, project_id, minimum_role="analyst")
    source: dict[str, object]
    if payload.snapshot_id:
        snapshot = await snapshot_or_404(db, user, payload.snapshot_id, minimum_role="analyst")
        if snapshot.project_id != project.id:
            raise AppError(
                422,
                "Snapshot mismatch",
                "Use a snapshot from this project.",
                code="scope",
            )
        source = {
            "snapshot_id": snapshot.id,
            "snapshot_name": snapshot.name,
            "snapshot_version": snapshot.version,
            "snapshot_type": snapshot.snapshot_type,
            "generated_from_dataset_id": snapshot.dataset_id,
        }
        analysis_snapshot_id = snapshot.id
        dataset = await db.get(Dataset, snapshot.dataset_id) if snapshot.dataset_id else None
        source.update(
            {
                "import_source_type": dataset.source_type if dataset else "derived",
                "imported_at": dataset.created_at.isoformat() if dataset else None,
                "imported_by": dataset.created_by if dataset else None,
                "node_count": int(
                    await db.scalar(
                        select(func.count(DirectoryNode.id)).where(DirectoryNode.snapshot_id == snapshot.id)
                    )
                    or 0
                ),
                "relationship_count": int(
                    await db.scalar(
                        select(func.count(DirectoryRelationship.id)).where(
                            DirectoryRelationship.snapshot_id == snapshot.id
                        )
                    )
                    or 0
                ),
                "path_count": int(
                    await db.scalar(
                        select(func.count(PrivilegePath.id))
                        .join(PathAnalysis, PathAnalysis.id == PrivilegePath.path_analysis_id)
                        .where(PathAnalysis.snapshot_id == snapshot.id)
                    )
                    or 0
                ),
                "remediation_plan_count": int(
                    await db.scalar(
                        select(func.count(RemediationPlan.id)).where(RemediationPlan.source_snapshot_id == snapshot.id)
                    )
                    or 0
                ),
            }
        )
        findings = list(
            (
                await db.scalars(
                    select(RiskFinding)
                    .where(RiskFinding.snapshot_id == snapshot.id)
                    .order_by(
                        case({"critical": 0, "high": 1, "medium": 2, "low": 3}, value=RiskFinding.severity, else_=4),
                        RiskFinding.internal_score.desc(),
                        RiskFinding.title,
                    )
                )
            ).all()
        )
    else:
        comparison = await db.get(SnapshotComparison, payload.comparison_id)
        if not comparison or comparison.project_id != project.id:
            raise AppError(
                404,
                "Comparison not found",
                "The comparison does not exist.",
                code="not_found",
            )
        source = {
            "comparison_id": comparison.id,
            "before_snapshot_id": comparison.before_snapshot_id,
            "after_snapshot_id": comparison.after_snapshot_id,
            "metrics": {
                "nodes_added": comparison.nodes_added,
                "nodes_removed": comparison.nodes_removed,
                "relationships_added": comparison.relationships_added,
                "relationships_removed": comparison.relationships_removed,
                "risk_score_before": comparison.risk_score_before,
                "risk_score_after": comparison.risk_score_after,
                "findings_added": comparison.findings_added,
                "findings_resolved": comparison.findings_resolved,
                "findings_reopened": comparison.findings_reopened,
                "severity_changes": comparison.severity_changes,
                "remediation_outcomes": comparison.remediation_outcomes,
            },
        }
        analysis_snapshot_id = comparison.after_snapshot_id
        findings = list(
            (await db.scalars(select(RiskFinding).where(RiskFinding.snapshot_id == comparison.after_snapshot_id))).all()
        )

    latest = await db.scalar(
        select(PathAnalysis)
        .where(PathAnalysis.snapshot_id == analysis_snapshot_id, PathAnalysis.status == "complete")
        .order_by(PathAnalysis.completed_at.desc(), PathAnalysis.id.desc())
        .limit(1)
    )
    if payload.analysis_id:
        latest = await db.get(PathAnalysis, payload.analysis_id)
        if not latest or latest.snapshot_id != analysis_snapshot_id or latest.status != "complete":
            raise AppError(422, "Analysis mismatch", "Select a completed analysis from this snapshot.", code="scope")
    paths = (await _analysis_response(db, latest)).paths if latest else []
    source["path_count"] = len(paths)
    source["analysis_available"] = latest is not None
    source["path_scope"] = (
        "Selected completed analysis; bounded traversal of imported relationships."
        if payload.analysis_id
        else "Most recent completed analysis; bounded traversal of imported relationships."
    )
    source["analysis_id"] = latest.id if latest else None
    source["analysis_parameters"] = latest.request_json if latest else {}
    source["analysis_truncated"] = bool(latest and latest.request_json.get("truncated"))
    source["report_type"] = payload.report_type
    source["important_paths"] = [
        {
            "source": path.steps[0].source_name,
            "target": path.steps[-1].target_name,
            "risk_score": path.risk_score,
            "severity": path_severity(path.risk_score),
            "confidence": path.confidence,
            "relationships": [step.model_dump() for step in path.steps],
            "explanation": path.explanation,
            "limitations": path.limitations,
        }
        for path in sorted(paths, key=lambda path: -path.risk_score)
        if path.steps
    ]
    grouped: dict[str, dict[str, Any]] = {}
    for path in paths:
        for step in path.steps:
            if step.relationship_id not in grouped:
                grouped[step.relationship_id] = {
                    "title": f"Review {step.source_name} → {step.target_name}",
                    "action": step.remediation_summary,
                    "affected_paths": 0,
                }
            grouped[step.relationship_id]["affected_paths"] += 1
    source["priority_fixes"] = sorted(grouped.values(), key=lambda fix: -fix["affected_paths"])

    extension = payload.format
    storage_name = f"{uuid4()}.{extension}"
    storage_path = settings.report_storage_path.resolve() / storage_name
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    file_hash, size_bytes, mime_type = generate_report(
        output_path=storage_path,
        output_format=payload.format,
        project={"id": project.id, "name": project.name},
        source=source,
        findings=[_finding_dict(item) for item in findings],
    )
    report = Report(
        project_id=project.id,
        snapshot_id=payload.snapshot_id,
        comparison_id=payload.comparison_id,
        report_type=payload.report_type,
        format=payload.format,
        status="complete",
        content_version="1.0",
        mime_type=mime_type,
        generated_by=user.id,
        file_name=f"adpathlens-{payload.report_type}-{storage_name[:8]}.{extension}",
        file_hash=file_hash,
        storage_path=str(storage_path),
        size_bytes=size_bytes,
    )
    db.add(report)
    await db.flush()
    await record_audit(
        db,
        request,
        "report.generated",
        "report",
        "Sanitized report generated",
        user=user,
        entity_id=report.id,
        project_id=project.id,
        context={"format": report.format, "size_bytes": size_bytes},
    )
    await db.commit()
    await db.refresh(report)
    return report


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, db: DB, user: CurrentUser) -> Report:
    return await _report_or_404(db, user, report_id)


@router.get("/reports/{report_id}/download", response_class=FileResponse)
async def download_report(report_id: str, request: Request, db: DB, user: CurrentUser) -> FileResponse:
    report = await _report_or_404(db, user, report_id)
    path = _available_report_path(report.storage_path)
    if path is None:
        raise AppError(
            410,
            "Report unavailable",
            "The generated report file is no longer available.",
            code="file_missing",
        )
    await record_audit(
        db,
        request,
        "report.downloaded",
        "report",
        "Authorized report downloaded",
        user=user,
        entity_id=report.id,
        project_id=report.project_id,
        context={"format": report.format, "size_bytes": report.size_bytes},
    )
    await db.commit()
    return FileResponse(
        path,
        media_type=report.mime_type,
        filename=report.file_name,
        headers={
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )
