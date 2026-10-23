import csv
import io
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import DB, CurrentUser, EditorCsrf
from app.audit.service import record_audit
from app.core.errors import AppError
from app.models.entities import (
    DirectoryNode,
    DirectoryRelationship,
    PathAnalysis,
    PrivilegePath,
    RiskFinding,
    SnapshotComparison,
    User,
)
from app.reporting.service import safe_csv_cell
from app.schemas.comparisons import (
    ComparisonCreate,
    ComparisonItemPage,
    ComparisonResponse,
)
from app.services.authorization import project_or_404, snapshot_or_404

router = APIRouter(tags=["comparisons"])


async def _comparison_or_404(db: DB, user: User, comparison_id: str) -> SnapshotComparison:
    comparison = await db.get(SnapshotComparison, comparison_id)
    if not comparison:
        raise AppError(
            404,
            "Comparison not found",
            "The comparison does not exist.",
            code="not_found",
        )
    await project_or_404(db, user, comparison.project_id)
    return comparison


def _changed_fields(before: Any, after: Any, fields: tuple[str, ...]) -> dict[str, dict[str, object]]:
    changes: dict[str, dict[str, object]] = {}
    for field in fields:
        old = getattr(before, field)
        new = getattr(after, field)
        if old != new:
            changes[field] = {"before": old, "after": new}
    return changes


async def _create_diff(
    db: DB, before_id: str, after_id: str
) -> tuple[dict[str, list[dict[str, object]]], dict[str, Any]]:
    before_nodes = {
        item.external_id: item
        for item in (await db.scalars(select(DirectoryNode).where(DirectoryNode.snapshot_id == before_id))).all()
    }
    after_nodes = {
        item.external_id: item
        for item in (await db.scalars(select(DirectoryNode).where(DirectoryNode.snapshot_id == after_id))).all()
    }
    overlap = set(before_nodes) & set(after_nodes)
    minimum_size = min(len(before_nodes), len(after_nodes))
    if minimum_size and len(overlap) / minimum_size < 0.1:
        raise AppError(
            422,
            "Snapshots are not comparable",
            "Snapshots have insufficient stable external-ID overlap.",
            code="identity_overlap",
        )

    node_added: list[dict[str, object]] = []
    for key in sorted(set(after_nodes) - set(before_nodes)):
        node_added.append(
            {
                "change": "added",
                "external_id": key,
                "node_type": after_nodes[key].node_type,
                "name": after_nodes[key].display_name,
            }
        )
    node_removed: list[dict[str, object]] = []
    for key in sorted(set(before_nodes) - set(after_nodes)):
        node_removed.append(
            {
                "change": "removed",
                "external_id": key,
                "node_type": before_nodes[key].node_type,
                "name": before_nodes[key].display_name,
            }
        )
    node_changed: list[dict[str, object]] = []
    for key in sorted(overlap):
        changes = _changed_fields(
            before_nodes[key],
            after_nodes[key],
            (
                "node_type",
                "display_name",
                "enabled",
                "high_value",
                "privileged",
                "risk_level",
            ),
        )
        if changes:
            node_changed.append({"change": "changed", "external_id": key, "fields": changes})

    before_relationships = {
        item.external_id: item
        for item in (
            await db.scalars(select(DirectoryRelationship).where(DirectoryRelationship.snapshot_id == before_id))
        ).all()
    }
    after_relationships = {
        item.external_id: item
        for item in (
            await db.scalars(select(DirectoryRelationship).where(DirectoryRelationship.snapshot_id == after_id))
        ).all()
    }
    relationship_added: list[dict[str, object]] = []
    for key in sorted(set(after_relationships) - set(before_relationships)):
        relationship_added.append(
            {
                "change": "added",
                "external_id": key,
                "relationship_type": after_relationships[key].relationship_type,
            }
        )
    relationship_removed: list[dict[str, object]] = []
    for key in sorted(set(before_relationships) - set(after_relationships)):
        relationship_removed.append(
            {
                "change": "removed",
                "external_id": key,
                "relationship_type": before_relationships[key].relationship_type,
            }
        )
    relationship_changed: list[dict[str, object]] = []
    for key in sorted(set(before_relationships) & set(after_relationships)):
        changes = _changed_fields(
            before_relationships[key],
            after_relationships[key],
            (
                "relationship_type",
                "active",
                "confidence",
                "inherited",
                "risk_weight",
            ),
        )
        if changes:
            relationship_changed.append({"change": "changed", "external_id": key, "fields": changes})

    before_paths = {
        item.path_signature: item
        for item in (
            await db.scalars(
                select(PrivilegePath)
                .join(PathAnalysis, PathAnalysis.id == PrivilegePath.path_analysis_id)
                .where(PathAnalysis.snapshot_id == before_id)
            )
        ).all()
    }
    after_paths = {
        item.path_signature: item
        for item in (
            await db.scalars(
                select(PrivilegePath)
                .join(PathAnalysis, PathAnalysis.id == PrivilegePath.path_analysis_id)
                .where(PathAnalysis.snapshot_id == after_id)
            )
        ).all()
    }
    paths: list[dict[str, object]] = []
    for key in sorted(set(after_paths) - set(before_paths)):
        paths.append({"change": "added", "signature": key})
    for key in sorted(set(before_paths) - set(after_paths)):
        paths.append({"change": "removed", "signature": key})

    before_findings = list((await db.scalars(select(RiskFinding).where(RiskFinding.snapshot_id == before_id))).all())
    after_findings = list((await db.scalars(select(RiskFinding).where(RiskFinding.snapshot_id == after_id))).all())
    before_by_key = {
        item.stable_fingerprint or f"{item.rule_id or 'manual'}:{item.title}": item for item in before_findings
    }
    after_by_key = {
        item.stable_fingerprint or f"{item.rule_id or 'manual'}:{item.title}": item for item in after_findings
    }
    finding_items: list[dict[str, object]] = []
    for key in sorted(set(after_by_key) - set(before_by_key)):
        finding_items.append(
            {
                "change": "added",
                "identity": key,
                "severity": after_by_key[key].severity,
            }
        )
    for key in sorted(set(before_by_key) - set(after_by_key)):
        finding_items.append(
            {
                "change": "removed",
                "identity": key,
                "severity": before_by_key[key].severity,
            }
        )
    severity_items: list[dict[str, object]] = []
    reopened_items: list[dict[str, object]] = []
    for key in sorted(set(before_by_key) & set(after_by_key)):
        old = before_by_key[key]
        new = after_by_key[key]
        if old.severity != new.severity or old.internal_score != new.internal_score:
            severity_items.append(
                {
                    "identity": key,
                    "severity_before": old.severity,
                    "severity_after": new.severity,
                    "score_before": old.internal_score,
                    "score_after": new.internal_score,
                }
            )
        if old.status in {"resolved", "closed", "false_positive"} and new.status not in {
            "resolved",
            "closed",
            "false_positive",
        }:
            reopened_items.append(
                {
                    "change": "reopened",
                    "identity": key,
                    "status_before": old.status,
                    "status_after": new.status,
                }
            )

    common_paths = set(before_paths) & set(after_paths)
    common_relationships = set(before_relationships) & set(after_relationships)
    unchanged_relationships = common_relationships - {str(item["external_id"]) for item in relationship_changed}
    unchanged_nodes = overlap - {str(item["external_id"]) for item in node_changed}
    removed_path_count = len(set(before_paths) - set(after_paths))
    added_path_count = len(set(after_paths) - set(before_paths))
    remediation_summary: dict[str, object] = {
        "path_removed": removed_path_count > 0,
        "path_shortened": False,
        "path_changed": bool(removed_path_count and added_path_count),
        "finding_resolved": len(set(before_by_key) - set(after_by_key)) > 0,
        "finding_reopened": bool(reopened_items),
        "no_measurable_change": not any(
            (
                node_added,
                node_removed,
                node_changed,
                relationship_added,
                relationship_removed,
                relationship_changed,
                paths,
                finding_items,
                severity_items,
            )
        ),
        "new_risk_introduced": added_path_count > removed_path_count
        or sum(item.internal_score for item in after_findings) > sum(item.internal_score for item in before_findings),
        "verification_unavailable": not before_paths and not after_paths,
    }

    items: dict[str, list[dict[str, object]]] = {
        "nodes": node_added + node_removed + node_changed,
        "relationships": relationship_added + relationship_removed + relationship_changed,
        "paths": paths,
        "findings": finding_items,
        "severity": severity_items,
        "remediation": [remediation_summary],
        "reopened": reopened_items,
    }
    metrics: dict[str, Any] = {
        "nodes_added": len(node_added),
        "nodes_removed": len(node_removed),
        "nodes_changed": len(node_changed),
        "nodes_unchanged": len(unchanged_nodes),
        "relationships_added": len(relationship_added),
        "relationships_removed": len(relationship_removed),
        "relationships_changed": len(relationship_changed),
        "relationships_unchanged": len(unchanged_relationships),
        "paths_added": added_path_count,
        "paths_removed": removed_path_count,
        "paths_unchanged": len(common_paths),
        "findings_added": len(set(after_by_key) - set(before_by_key)),
        "findings_resolved": len(set(before_by_key) - set(after_by_key)),
        "findings_reopened": len(reopened_items),
        "severity_changes": len(severity_items),
        "risk_score_before": round(sum(item.internal_score for item in before_findings), 2),
        "risk_score_after": round(sum(item.internal_score for item in after_findings), 2),
    }
    metrics["remediation_outcomes"] = remediation_summary
    return items, metrics


@router.post(
    "/projects/{project_id}/comparisons",
    response_model=ComparisonResponse,
    status_code=201,
)
async def create_comparison(
    project_id: str,
    payload: ComparisonCreate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> SnapshotComparison:
    await project_or_404(db, user, project_id, minimum_role="analyst")
    before = await snapshot_or_404(db, user, payload.before_snapshot_id, minimum_role="analyst")
    after = await snapshot_or_404(db, user, payload.after_snapshot_id, minimum_role="analyst")
    if before.id == after.id:
        raise AppError(
            422,
            "Snapshots must differ",
            "Choose two different snapshots.",
            code="same_snapshot",
        )
    if before.project_id != project_id or after.project_id != project_id:
        raise AppError(
            422,
            "Snapshot mismatch",
            "Both snapshots must belong to this project.",
            code="scope",
        )
    items, metrics = await _create_diff(db, before.id, after.id)
    comparison = SnapshotComparison(
        project_id=project_id,
        before_snapshot_id=before.id,
        after_snapshot_id=after.id,
        diff_json=items,
        created_by=user.id,
        **metrics,
    )
    db.add(comparison)
    await db.flush()
    await record_audit(
        db,
        request,
        "comparison.created",
        "comparison",
        "Snapshot comparison created",
        user=user,
        entity_id=comparison.id,
        project_id=project_id,
        context={
            "before_snapshot_id": before.id,
            "after_snapshot_id": after.id,
        },
    )
    await db.commit()
    await db.refresh(comparison)
    return comparison


@router.get(
    "/projects/{project_id}/comparisons",
    response_model=list[ComparisonResponse],
)
async def list_comparisons(project_id: str, db: DB, user: CurrentUser) -> list[SnapshotComparison]:
    await project_or_404(db, user, project_id)
    return list(
        (
            await db.scalars(
                select(SnapshotComparison)
                .where(SnapshotComparison.project_id == project_id)
                .order_by(SnapshotComparison.created_at.desc())
            )
        ).all()
    )


@router.get("/comparisons/{comparison_id}", response_model=ComparisonResponse)
async def get_comparison(comparison_id: str, db: DB, user: CurrentUser) -> SnapshotComparison:
    return await _comparison_or_404(db, user, comparison_id)


@router.get("/comparisons/{comparison_id}/export")
async def export_comparison(
    comparison_id: str,
    db: DB,
    user: CurrentUser,
) -> StreamingResponse:
    comparison = await _comparison_or_404(db, user, comparison_id)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["category", "change", "identity", "details"])
    for category in sorted(comparison.diff_json):
        values = comparison.diff_json.get(category, [])
        if not isinstance(values, list):
            continue
        for item in values[:10_000]:
            if not isinstance(item, dict):
                continue
            identity = item.get("external_id") or item.get("identity") or item.get("signature") or ""
            writer.writerow(
                [
                    safe_csv_cell(category),
                    safe_csv_cell(item.get("change", "")),
                    safe_csv_cell(identity),
                    safe_csv_cell(str(item)),
                ]
            )
    content = output.getvalue().encode("utf-8-sig")
    filename = f"adpathlens-comparison-{comparison.id[:8]}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/comparisons/{comparison_id}/{category}",
    response_model=ComparisonItemPage,
)
async def comparison_items(
    comparison_id: str,
    category: str,
    db: DB,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ComparisonItemPage:
    comparison = await _comparison_or_404(db, user, comparison_id)
    allowed = {"nodes", "relationships", "paths", "findings", "severity", "remediation", "reopened"}
    if category not in allowed:
        raise AppError(
            404,
            "Comparison category not found",
            "Choose nodes, relationships, paths, findings, severity, remediation, or reopened.",
            code="not_found",
        )
    raw = comparison.diff_json.get(category, [])
    items = raw if isinstance(raw, list) else []
    start = (page - 1) * page_size
    return ComparisonItemPage(
        comparison_id=comparison.id,
        category=category,
        items=items[start : start + page_size],
        page=page,
        page_size=page_size,
        total=len(items),
    )
