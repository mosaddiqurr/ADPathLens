from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import DB, CurrentUser, EditorCsrf
from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.entities import Report, RiskFinding, SnapshotComparison, User
from app.reporting.service import generate_report
from app.schemas.reports import ReportCreate, ReportResponse
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
        }
        findings = list(
            (
                await db.scalars(
                    select(RiskFinding)
                    .where(RiskFinding.snapshot_id == snapshot.id)
                    .order_by(RiskFinding.severity.desc(), RiskFinding.title)
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
            },
        }
        findings = list(
            (await db.scalars(select(RiskFinding).where(RiskFinding.snapshot_id == comparison.after_snapshot_id))).all()
        )

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
        context={"format": report.format, "size_bytes": size_bytes},
    )
    await db.commit()
    await db.refresh(report)
    return report


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, db: DB, user: CurrentUser) -> Report:
    return await _report_or_404(db, user, report_id)


@router.get("/reports/{report_id}/download", response_class=FileResponse)
async def download_report(report_id: str, db: DB, user: CurrentUser) -> FileResponse:
    report = await _report_or_404(db, user, report_id)
    path = _available_report_path(report.storage_path)
    if path is None:
        raise AppError(
            410,
            "Report unavailable",
            "The generated report file is no longer available.",
            code="file_missing",
        )
    return FileResponse(
        path,
        media_type=report.mime_type,
        filename=report.file_name,
        headers={
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )
