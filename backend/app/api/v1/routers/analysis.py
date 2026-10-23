from __future__ import annotations

import time
from functools import partial
from typing import Any

import anyio
import networkx as nx
from fastapi import APIRouter, Request
from sqlalchemy import select

from app.analysis.pathfinding import PathResult, explain_path, find_paths
from app.api.deps import DB, CurrentUser, EditorCsrf
from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.errors import AppError
from app.graph.service import build_graph
from app.models.entities import (
    DirectoryNode,
    DirectoryRelationship,
    PathAnalysis,
    PrivilegePath,
    PrivilegePathStep,
    utc_now,
)
from app.schemas.graph import (
    AnalysisRequest,
    AnalysisResponse,
    PathResponse,
    PathStepResponse,
)
from app.scoring.path_priority import path_severity
from app.services.authorization import project_or_404, snapshot_or_404

router = APIRouter(tags=["analysis"])
analysis_limiter = anyio.CapacityLimiter(5)
settings = get_settings()


async def _analysis_response(db: DB, analysis: PathAnalysis) -> AnalysisResponse:
    paths = list(
        (
            await db.scalars(
                select(PrivilegePath).where(PrivilegePath.path_analysis_id == analysis.id).order_by(PrivilegePath.rank)
            )
        ).all()
    )
    response_paths: list[PathResponse] = []
    for path in paths:
        steps = list(
            (
                await db.scalars(
                    select(PrivilegePathStep)
                    .where(PrivilegePathStep.privilege_path_id == path.id)
                    .order_by(PrivilegePathStep.position)
                )
            ).all()
        )
        node_ids = {step.source_node_id for step in steps} | {step.target_node_id for step in steps}
        relationship_ids = {step.relationship_id for step in steps}
        nodes = {
            node.id: node
            for node in (await db.scalars(select(DirectoryNode).where(DirectoryNode.id.in_(node_ids)))).all()
        }
        relationships = {
            relationship.id: relationship
            for relationship in (
                await db.scalars(select(DirectoryRelationship).where(DirectoryRelationship.id.in_(relationship_ids)))
            ).all()
        }
        response_paths.append(
            PathResponse(
                id=path.id,
                rank=path.rank,
                total_weight=path.total_weight,
                hop_count=path.hop_count,
                risk_score=path.risk_score,
                severity=path_severity(path.risk_score),
                scoring_components=path.scoring_components,
                confidence=path.confidence,
                explanation=path.explanation,
                limitations=path.limitations,
                steps=[
                    PathStepResponse(
                        position=step.position,
                        source_node_id=step.source_node_id,
                        source_name=nodes[step.source_node_id].display_name,
                        source_type=nodes[step.source_node_id].node_type,
                        relationship_id=step.relationship_id,
                        relationship_type=relationships[step.relationship_id].relationship_type,
                        target_node_id=step.target_node_id,
                        target_name=nodes[step.target_node_id].display_name,
                        target_type=nodes[step.target_node_id].node_type,
                        step_explanation=step.step_explanation,
                        remediation_summary=step.remediation_summary,
                        confidence=relationships[step.relationship_id].confidence,
                        risk_weight=relationships[step.relationship_id].risk_weight,
                        evidence=step.evidence_json,
                    )
                    for step in steps
                ],
            )
        )
    return AnalysisResponse(
        request_parameters=analysis.request_json,
        id=analysis.id,
        project_id=analysis.project_id,
        snapshot_id=analysis.snapshot_id,
        start_node_id=analysis.start_node_id,
        target_node_id=analysis.target_node_id,
        algorithm=analysis.algorithm,
        maximum_depth=analysis.maximum_depth,
        path_count=analysis.path_count,
        status=analysis.status,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        truncated=bool(analysis.request_json.get("truncated", False)),
        paths=response_paths,
    )


def _reverse_paths(
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]],
    target: str,
    payload: AnalysisRequest,
) -> tuple[list[PathResult], bool]:
    eligible: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]] = nx.MultiDiGraph()
    eligible.add_nodes_from(graph.nodes(data=True))
    for source, destination, key, data in graph.edges(keys=True, data=True):
        if (
            data["active"]
            and data["path_eligible"]
            and data["type"] not in payload.excluded_relationship_types
            and (not payload.relationship_types or data["type"] in payload.relationship_types)
        ):
            eligible.add_edge(source, destination, key=key, **data)
    relationship_types = {str(data["type"]) for _, _, _, data in eligible.edges(keys=True, data=True)}
    sources = sorted(
        (
            node
            for node in nx.ancestors(eligible, target)
            if not graph.nodes[node]["privileged"]
            and (payload.include_disabled or graph.nodes[node]["enabled"])
            and (not payload.source_node_types or graph.nodes[node].get("type") in payload.source_node_types)
        ),
        key=lambda node: (str(graph.nodes[node]["display_name"]).lower(), node),
    )
    paths: list[PathResult] = []
    truncated = False
    started = time.monotonic()
    remaining_expansions = settings.max_analysis_expansions
    for index, source in enumerate(sources):
        remaining_seconds = settings.analysis_deadline_seconds - (time.monotonic() - started)
        if remaining_seconds <= 0 or remaining_expansions <= 0:
            truncated = True
            break
        # Share one work budget across the complete reverse query.
        source_budget = max(1, remaining_expansions // (len(sources) - index))
        found, limited = find_paths(
            graph,
            source,
            {target},
            algorithm="shortest_hops",
            maximum_depth=payload.maximum_depth,
            maximum_paths=1,
            relationship_types=relationship_types,
            minimum_confidence=payload.minimum_confidence,
            include_disabled=payload.include_disabled,
            deadline_seconds=remaining_seconds,
            maximum_expansions=source_budget,
        )
        remaining_expansions -= source_budget
        paths.extend(found)
        truncated = truncated or limited
    paths.sort(key=lambda path: (3 * path.total_weight + len(path.edges), path.nodes, path.edges))
    truncated = truncated or len(paths) > payload.maximum_paths
    return paths[: payload.maximum_paths], truncated


@router.post("/snapshots/{snapshot_id}/analyses", response_model=AnalysisResponse, status_code=201)
async def create_analysis(
    snapshot_id: str,
    payload: AnalysisRequest,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> AnalysisResponse:
    snapshot = await snapshot_or_404(db, user, snapshot_id, minimum_role="analyst")
    start = await db.get(DirectoryNode, payload.start_node_id)
    if not start or start.snapshot_id != snapshot.id:
        raise AppError(422, "Invalid start node", "Select a node from this snapshot.", code="node")
    if (
        payload.algorithm != "reverse_reachability"
        and payload.source_node_types
        and start.node_type not in payload.source_node_types
    ):
        raise AppError(
            422,
            "Start node type excluded",
            "The selected source does not match the source object-type filter.",
            code="source_type",
        )
    target: DirectoryNode | None = None
    if payload.target_node_id:
        target = await db.get(DirectoryNode, payload.target_node_id)
        if not target or target.snapshot_id != snapshot.id:
            raise AppError(422, "Invalid target node", "Select a node from this snapshot.", code="node")
    analysis = PathAnalysis(
        project_id=snapshot.project_id,
        snapshot_id=snapshot.id,
        start_node_id=start.id,
        target_node_id=target.id if target else None,
        algorithm=payload.algorithm,
        maximum_depth=payload.maximum_depth,
        request_json=payload.model_dump(),
        initiated_by=user.id,
    )
    db.add(analysis)
    await db.flush()
    graph = await build_graph(db, snapshot.id)
    if payload.target_kind == "specific":
        targets = {str(payload.target_node_id)}
    elif payload.target_kind == "high_value":
        targets = {node for node, data in graph.nodes(data=True) if data["high_value"]}
    else:
        targets = {node for node, data in graph.nodes(data=True) if data["privileged"]}
    if payload.target_node_types:
        targets = {node for node in targets if str(graph.nodes[node]["type"]) in payload.target_node_types}
    if not targets:
        raise AppError(422, "No eligible target", "No target matches this selection.", code="no_target")
    relationship_types = set(payload.relationship_types)
    if not relationship_types:
        relationship_types = {str(data["type"]) for _, _, _, data in graph.edges(keys=True, data=True)}
    relationship_types -= set(payload.excluded_relationship_types)
    if payload.algorithm == "reverse_reachability":
        run = partial(_reverse_paths, graph, str(payload.target_node_id), payload)
    else:
        run = partial(
            find_paths,
            graph,
            start.id,
            targets,
            algorithm=payload.algorithm,
            maximum_depth=payload.maximum_depth,
            maximum_paths=payload.maximum_paths,
            relationship_types=relationship_types,
            minimum_confidence=payload.minimum_confidence,
            include_disabled=payload.include_disabled,
            deadline_seconds=settings.analysis_deadline_seconds,
            maximum_expansions=settings.max_analysis_expansions,
        )
    results, truncated = await anyio.to_thread.run_sync(run, limiter=analysis_limiter)
    results.sort(key=lambda path: (3 * path.total_weight + len(path.edges), path.nodes, path.edges))
    analysis.request_json = {**analysis.request_json, "truncated": truncated}
    for rank, result in enumerate(results, start=1):
        summary, steps = explain_path(graph, result)
        risk_score = max(0.0, min(100.0, 100 - result.total_weight * 3 - len(result.edges)))
        scoring_components = {
            "base": 100.0,
            "weighted_relationship_penalty": round(result.total_weight * 3, 2),
            "hop_penalty": len(result.edges),
            "destination_high_value": bool(graph.nodes[result.nodes[-1]].get("high_value")),
            "confidence": result.confidence,
            "interpretation": (
                "A higher score prioritizes review of shorter, stronger modeled control relationships; "
                "it is not certainty of compromise."
            ),
        }
        path = PrivilegePath(
            path_analysis_id=analysis.id,
            rank=rank,
            path_signature=result.signature,
            total_weight=result.total_weight,
            hop_count=len(result.edges),
            risk_score=risk_score,
            scoring_components=scoring_components,
            confidence=result.confidence,
            explanation=summary,
            limitations=(
                "This possible privilege path is derived from imported relationships and "
                "does not prove exploitation or compromise."
            ),
        )
        db.add(path)
        await db.flush()
        for step in steps:
            db.add(
                PrivilegePathStep(
                    privilege_path_id=path.id,
                    position=step["position"],
                    source_node_id=step["source_node_id"],
                    relationship_id=step["relationship_id"],
                    target_node_id=step["target_node_id"],
                    step_explanation=step["explanation"],
                    remediation_summary=step["remediation"],
                    evidence_json=step["evidence"],
                )
            )
    analysis.path_count = len(results)
    analysis.status = "complete"
    analysis.completed_at = utc_now()
    await record_audit(
        db,
        request,
        "analysis.completed",
        "analysis",
        f"Path analysis completed with {len(results)} result(s)",
        user=user,
        entity_id=analysis.id,
        project_id=snapshot.project_id,
        context={"snapshot_id": snapshot.id, "algorithm": payload.algorithm},
    )
    await db.commit()
    await db.refresh(analysis)
    return await _analysis_response(db, analysis)


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(analysis_id: str, db: DB, user: CurrentUser) -> AnalysisResponse:
    analysis = await db.get(PathAnalysis, analysis_id)
    if not analysis:
        raise AppError(404, "Analysis not found", "The analysis does not exist.", code="not_found")
    await project_or_404(db, user, analysis.project_id)
    return await _analysis_response(db, analysis)


@router.get("/paths/{path_id}", response_model=PathResponse)
async def get_path(path_id: str, db: DB, user: CurrentUser) -> PathResponse:
    path = await db.get(PrivilegePath, path_id)
    if not path:
        raise AppError(404, "Path not found", "The path does not exist.", code="not_found")
    analysis = await db.get(PathAnalysis, path.path_analysis_id)
    if not analysis:
        raise AppError(404, "Analysis not found", "The analysis does not exist.", code="not_found")
    await project_or_404(db, user, analysis.project_id)
    response = await _analysis_response(db, analysis)
    return next(item for item in response.paths if item.id == path_id)


@router.get("/snapshots/{snapshot_id}/analyses/latest", response_model=AnalysisResponse | None)
async def latest_analysis(snapshot_id: str, db: DB, user: CurrentUser) -> AnalysisResponse | None:
    """Restore the most recent completed analysis without rerunning or accumulating counts."""
    await snapshot_or_404(db, user, snapshot_id)
    analysis = await db.scalar(
        select(PathAnalysis)
        .where(PathAnalysis.snapshot_id == snapshot_id, PathAnalysis.status == "complete")
        .order_by(PathAnalysis.completed_at.desc(), PathAnalysis.id.desc())
        .limit(1)
    )
    return await _analysis_response(db, analysis) if analysis else None
