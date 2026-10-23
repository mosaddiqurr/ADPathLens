from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser, EditorCsrf
from app.audit.service import record_audit
from app.core.errors import AppError
from app.graph.service import graph_cache
from app.models.entities import (
    DirectoryNode,
    DirectoryRelationship,
    GraphSnapshot,
    RemediationAction,
    RemediationActionHistory,
    RemediationPlan,
    RiskFinding,
    User,
)
from app.schemas.remediation import (
    RemediationActionCreate,
    RemediationActionResponse,
    RemediationActionUpdate,
    RemediationHistoryResponse,
    RemediationPlanCreate,
    RemediationPlanResponse,
    RemediationPlanUpdate,
    RemediationPreviewResponse,
)
from app.services.authorization import project_or_404, snapshot_or_404

router = APIRouter(tags=["remediation"])


async def _plan_or_404(db: DB, user: User, plan_id: str, minimum_role: str = "viewer") -> RemediationPlan:
    plan = await db.get(RemediationPlan, plan_id)
    if not plan:
        raise AppError(404, "Remediation plan not found", "The plan does not exist.", code="not_found")
    await project_or_404(db, user, plan.project_id, minimum_role=minimum_role)
    return plan


@router.get(
    "/projects/{project_id}/remediation-plans",
    response_model=list[RemediationPlanResponse],
)
async def list_plans(project_id: str, db: DB, user: CurrentUser) -> list[RemediationPlan]:
    await project_or_404(db, user, project_id)
    return list(
        (
            await db.scalars(
                select(RemediationPlan)
                .where(RemediationPlan.project_id == project_id)
                .order_by(RemediationPlan.updated_at.desc())
            )
        ).all()
    )


@router.post(
    "/projects/{project_id}/remediation-plans",
    response_model=RemediationPlanResponse,
    status_code=201,
)
async def create_plan(
    project_id: str,
    payload: RemediationPlanCreate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> RemediationPlan:
    await project_or_404(db, user, project_id, minimum_role="analyst")
    snapshot = await snapshot_or_404(db, user, payload.source_snapshot_id, minimum_role="analyst")
    if snapshot.project_id != project_id:
        raise AppError(422, "Snapshot mismatch", "Use a snapshot from this project.", code="scope")
    plan = RemediationPlan(
        project_id=project_id,
        source_snapshot_id=snapshot.id,
        name=payload.name,
        description=payload.description,
        created_by=user.id,
    )
    db.add(plan)
    await db.flush()
    await record_audit(
        db,
        request,
        "remediation.plan_created",
        "remediation_plan",
        "Remediation plan created",
        user=user,
        entity_id=plan.id,
        project_id=plan.project_id,
    )
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/remediation-plans/{plan_id}", response_model=RemediationPlanResponse)
async def get_plan(plan_id: str, db: DB, user: CurrentUser) -> RemediationPlan:
    return await _plan_or_404(db, user, plan_id)


@router.patch("/remediation-plans/{plan_id}", response_model=RemediationPlanResponse)
async def update_plan(
    plan_id: str,
    payload: RemediationPlanUpdate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> RemediationPlan:
    plan = await _plan_or_404(db, user, plan_id, minimum_role="analyst")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    await record_audit(
        db,
        request,
        "remediation.plan_updated",
        "remediation_plan",
        "Remediation plan updated",
        user=user,
        entity_id=plan.id,
        project_id=plan.project_id,
    )
    await db.commit()
    await db.refresh(plan)
    return plan


@router.delete("/remediation-plans/{plan_id}", status_code=204)
async def delete_plan(plan_id: str, request: Request, db: DB, user: EditorCsrf) -> None:
    plan = await _plan_or_404(db, user, plan_id, minimum_role="analyst")
    derived_exists = await db.scalar(
        select(GraphSnapshot.id).where(GraphSnapshot.remediation_plan_id == plan.id).limit(1)
    )
    if derived_exists:
        raise AppError(
            409,
            "Plan has derived snapshots",
            "Plans used to create immutable derived snapshots cannot be deleted.",
            code="plan_in_use",
        )
    await record_audit(
        db,
        request,
        "remediation.plan_deleted",
        "remediation_plan",
        "Remediation plan deleted",
        user=user,
        entity_id=plan.id,
        project_id=plan.project_id,
    )
    await db.delete(plan)
    await db.commit()


@router.get(
    "/remediation-plans/{plan_id}/actions",
    response_model=list[RemediationActionResponse],
)
async def list_actions(plan_id: str, db: DB, user: CurrentUser) -> list[RemediationAction]:
    await _plan_or_404(db, user, plan_id)
    return list(
        (
            await db.scalars(
                select(RemediationAction)
                .where(RemediationAction.remediation_plan_id == plan_id)
                .order_by(RemediationAction.created_at)
            )
        ).all()
    )


@router.post(
    "/remediation-plans/{plan_id}/actions",
    response_model=RemediationActionResponse,
    status_code=201,
)
async def add_action(
    plan_id: str,
    payload: RemediationActionCreate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> RemediationAction:
    plan = await _plan_or_404(db, user, plan_id, minimum_role="analyst")
    before: dict[str, Any]
    if payload.target_node_id:
        node = await db.get(DirectoryNode, payload.target_node_id)
        if not node or node.snapshot_id != plan.source_snapshot_id:
            raise AppError(422, "Invalid node", "Select a node from the source snapshot.", code="node")
        before = {
            "enabled": node.enabled,
            "high_value": node.high_value,
            "external_id": node.external_id,
        }
    else:
        relationship = await db.get(DirectoryRelationship, payload.target_relationship_id)
        if not relationship or relationship.snapshot_id != plan.source_snapshot_id:
            raise AppError(
                422,
                "Invalid relationship",
                "Select a relationship from the source snapshot.",
                code="relationship",
            )
        before = {
            "active": relationship.active,
            "risk_weight": relationship.risk_weight,
            "external_id": relationship.external_id,
        }
    if payload.finding_id:
        finding = await db.get(RiskFinding, payload.finding_id)
        if not finding or finding.project_id != plan.project_id:
            raise AppError(422, "Invalid finding", "Select a finding from this project.", code="finding")
    if payload.assigned_to:
        assignee = await db.get(User, payload.assigned_to)
        if not assignee or not assignee.is_active:
            raise AppError(422, "Invalid assignee", "Select an active user.", code="assignee")
    action = RemediationAction(
        remediation_plan_id=plan.id,
        finding_id=payload.finding_id,
        action_type=payload.action_type,
        target_node_id=payload.target_node_id,
        target_relationship_id=payload.target_relationship_id,
        description=payload.description,
        proposed_change=payload.proposed_change,
        before_value=before,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        due_at=payload.due_at,
        expected_outcome=payload.expected_outcome,
    )
    db.add(action)
    await db.flush()
    db.add(
        RemediationActionHistory(
            remediation_action_id=action.id,
            previous_status=None,
            new_status=action.status,
            previous_progress=None,
            new_progress=action.progress_percent,
            note="Remediation action created.",
            changed_by=user.id,
        )
    )
    await record_audit(
        db,
        request,
        "remediation.action_added",
        "remediation_plan",
        "Simulation action added",
        user=user,
        entity_id=plan.id,
        project_id=plan.project_id,
        context={"action_type": payload.action_type},
    )
    await db.commit()
    await db.refresh(action)
    return action


@router.patch(
    "/remediation-actions/{action_id}",
    response_model=RemediationActionResponse,
)
async def update_action(
    action_id: str,
    payload: RemediationActionUpdate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> RemediationAction:
    action = await db.get(RemediationAction, action_id)
    if not action:
        raise AppError(
            404,
            "Remediation action not found",
            "The action does not exist.",
            code="not_found",
        )
    plan = await _plan_or_404(db, user, action.remediation_plan_id, minimum_role="analyst")
    changes = payload.model_dump(exclude_unset=True)
    history_note = changes.pop("history_note", "")
    if "assigned_to" in changes and changes["assigned_to"]:
        assignee = await db.get(User, changes["assigned_to"])
        if not assignee or not assignee.is_active:
            raise AppError(422, "Invalid assignee", "Select an active user.", code="assignee")
    previous_status = action.status
    previous_progress = action.progress_percent
    for key, value in changes.items():
        setattr(action, key, value)
    if action.status in {"completed", "verified"} and action.completed_at is None:
        action.completed_at = datetime.now(UTC)
    elif action.status not in {"completed", "verified"}:
        action.completed_at = None
    db.add(
        RemediationActionHistory(
            remediation_action_id=action.id,
            previous_status=previous_status,
            new_status=action.status,
            previous_progress=previous_progress,
            new_progress=action.progress_percent,
            note=history_note,
            changed_by=user.id,
        )
    )
    await record_audit(
        db,
        request,
        "remediation.action_updated",
        "remediation_plan",
        "Simulation action updated",
        user=user,
        entity_id=plan.id,
        project_id=plan.project_id,
    )
    await db.commit()
    await db.refresh(action)
    return action


@router.get(
    "/remediation-actions/{action_id}/history",
    response_model=list[RemediationHistoryResponse],
)
async def action_history(
    action_id: str,
    db: DB,
    user: CurrentUser,
) -> list[RemediationActionHistory]:
    action = await db.get(RemediationAction, action_id)
    if not action:
        raise AppError(404, "Remediation action not found", "The action does not exist.", code="not_found")
    await _plan_or_404(db, user, action.remediation_plan_id)
    return list(
        (
            await db.scalars(
                select(RemediationActionHistory)
                .where(RemediationActionHistory.remediation_action_id == action.id)
                .order_by(RemediationActionHistory.changed_at, RemediationActionHistory.id)
            )
        ).all()
    )


@router.delete("/remediation-actions/{action_id}", status_code=204)
async def delete_action(action_id: str, request: Request, db: DB, user: EditorCsrf) -> None:
    action = await db.get(RemediationAction, action_id)
    if not action:
        raise AppError(
            404,
            "Remediation action not found",
            "The action does not exist.",
            code="not_found",
        )
    plan = await _plan_or_404(db, user, action.remediation_plan_id, minimum_role="analyst")
    await record_audit(
        db,
        request,
        "remediation.action_deleted",
        "remediation_plan",
        "Simulation action deleted",
        user=user,
        entity_id=plan.id,
        project_id=plan.project_id,
    )
    await db.delete(action)
    await db.commit()


async def _preview_counts(db: DB, plan: RemediationPlan) -> RemediationPreviewResponse:
    source_nodes = list(
        (await db.scalars(select(DirectoryNode).where(DirectoryNode.snapshot_id == plan.source_snapshot_id))).all()
    )
    source_relationships = list(
        (
            await db.scalars(
                select(DirectoryRelationship).where(DirectoryRelationship.snapshot_id == plan.source_snapshot_id)
            )
        ).all()
    )
    actions = list(
        (await db.scalars(select(RemediationAction).where(RemediationAction.remediation_plan_id == plan.id))).all()
    )
    removed_nodes = {
        action.target_node_id for action in actions if action.action_type == "remove_node" and action.target_node_id
    }
    removed_relationships = {
        action.target_relationship_id
        for action in actions
        if action.target_relationship_id
        and action.action_type
        in {
            "remove_relationship",
            "remove_group_membership",
            "remove_local_admin",
            "remove_password_reset",
            "remove_gpo_control",
            "remove_privileged_session",
        }
    }
    remaining_relationships = [
        relationship
        for relationship in source_relationships
        if relationship.id not in removed_relationships
        and relationship.source_node_id not in removed_nodes
        and relationship.target_node_id not in removed_nodes
    ]
    return RemediationPreviewResponse(
        plan_id=plan.id,
        source_node_count=len(source_nodes),
        preview_node_count=len(source_nodes) - len(removed_nodes),
        source_relationship_count=len(source_relationships),
        preview_relationship_count=len(remaining_relationships),
        actions_applied=len(actions),
        warnings=[
            "Simulation only. No changes have been made to Active Directory.",
            "Path removal in a modeled graph does not prove the environment is secure.",
        ],
    )


@router.post(
    "/remediation-plans/{plan_id}/preview",
    response_model=RemediationPreviewResponse,
)
async def preview_plan(plan_id: str, request: Request, db: DB, user: EditorCsrf) -> RemediationPreviewResponse:
    plan = await _plan_or_404(db, user, plan_id, minimum_role="analyst")
    preview = await _preview_counts(db, plan)
    await record_audit(
        db,
        request,
        "remediation.previewed",
        "remediation_plan",
        "Remediation simulation previewed",
        user=user,
        entity_id=plan.id,
        project_id=plan.project_id,
    )
    await db.commit()
    return preview


@router.post(
    "/remediation-plans/{plan_id}/create-snapshot",
    response_model=dict[str, Any],
    status_code=201,
)
async def create_derived_snapshot(plan_id: str, request: Request, db: DB, user: EditorCsrf) -> dict[str, Any]:
    plan = await _plan_or_404(db, user, plan_id, minimum_role="analyst")
    source = await snapshot_or_404(db, user, plan.source_snapshot_id, minimum_role="analyst")
    actions = list(
        (await db.scalars(select(RemediationAction).where(RemediationAction.remediation_plan_id == plan.id))).all()
    )
    if not actions:
        raise AppError(422, "No remediation actions", "Add at least one simulation action.", code="empty_plan")
    next_version = (
        await db.scalar(
            select(func.coalesce(func.max(GraphSnapshot.version), 0)).where(
                GraphSnapshot.project_id == source.project_id
            )
        )
        or 0
    ) + 1
    derived = GraphSnapshot(
        project_id=source.project_id,
        dataset_id=source.dataset_id,
        parent_snapshot_id=source.id,
        remediation_plan_id=plan.id,
        name=f"{source.name} — simulated remediation",
        snapshot_type="derived",
        description="Simulation only. No changes have been made to Active Directory.",
        version=next_version,
        created_by=user.id,
    )
    db.add(derived)
    await db.flush()
    source_nodes = list((await db.scalars(select(DirectoryNode).where(DirectoryNode.snapshot_id == source.id))).all())
    source_relationships = list(
        (await db.scalars(select(DirectoryRelationship).where(DirectoryRelationship.snapshot_id == source.id))).all()
    )
    removed_node_ids = {
        action.target_node_id for action in actions if action.action_type == "remove_node" and action.target_node_id
    }
    node_actions = {
        action.target_node_id: action
        for action in actions
        if action.target_node_id and action.action_type != "remove_node"
    }
    node_mapping: dict[str, str] = {}
    for node in source_nodes:
        if node.id in removed_node_ids:
            continue
        action = node_actions.get(node.id)
        enabled = False if action and action.action_type == "disable_account" else node.enabled
        high_value = False if action and action.action_type == "mark_no_longer_high_value" else node.high_value
        clone = DirectoryNode(
            snapshot_id=derived.id,
            source_file_id=node.source_file_id,
            external_id=node.external_id,
            node_type=node.node_type,
            name=node.name,
            display_name=node.display_name,
            description=node.description,
            domain_name=node.domain_name,
            enabled=enabled,
            high_value=high_value,
            privileged=node.privileged,
            risk_level=node.risk_level,
            metadata_json={**node.metadata_json, "simulated_from_node_id": node.id},
            stable_fingerprint=node.stable_fingerprint,
            first_seen_at=node.first_seen_at,
            last_seen_at=derived.created_at,
        )
        db.add(clone)
        await db.flush()
        node_mapping[node.id] = clone.id
    removal_types = {
        "remove_relationship",
        "remove_group_membership",
        "remove_local_admin",
        "remove_password_reset",
        "remove_gpo_control",
        "remove_privileged_session",
    }
    relationship_actions = {
        action.target_relationship_id: action for action in actions if action.target_relationship_id
    }
    for relationship in source_relationships:
        action = relationship_actions.get(relationship.id)
        if (
            relationship.source_node_id not in node_mapping
            or relationship.target_node_id not in node_mapping
            or (action and action.action_type in removal_types)
        ):
            continue
        active = False if action and action.action_type == "disable_relationship" else relationship.active
        weight = relationship.risk_weight
        if action and action.action_type == "change_relationship_weight":
            weight = float(action.proposed_change.get("risk_weight", weight))
        db.add(
            DirectoryRelationship(
                snapshot_id=derived.id,
                source_file_id=relationship.source_file_id,
                external_id=relationship.external_id,
                source_node_id=node_mapping[relationship.source_node_id],
                target_node_id=node_mapping[relationship.target_node_id],
                relationship_type=relationship.relationship_type,
                direction=relationship.direction,
                inherited=relationship.inherited,
                active=active,
                risk_weight=weight,
                confidence=relationship.confidence,
                description=relationship.description,
                evidence_json=relationship.evidence_json,
                metadata_json={
                    **relationship.metadata_json,
                    "simulated_from_relationship_id": relationship.id,
                },
                stable_fingerprint=relationship.stable_fingerprint,
                first_seen_at=relationship.first_seen_at,
                last_seen_at=derived.created_at,
            )
        )
    plan.status = "simulated"
    await record_audit(
        db,
        request,
        "remediation.snapshot_created",
        "snapshot",
        "Derived simulation snapshot created",
        user=user,
        entity_id=derived.id,
        project_id=plan.project_id,
        context={"source_snapshot_id": source.id, "plan_id": plan.id},
    )
    await db.commit()
    graph_cache.invalidate(derived.id)
    preview = await _preview_counts(db, plan)
    return {
        "id": derived.id,
        "project_id": derived.project_id,
        "parent_snapshot_id": derived.parent_snapshot_id,
        "name": derived.name,
        "snapshot_type": derived.snapshot_type,
        "version": derived.version,
        "simulation_only": True,
        "preview": preview.model_dump(),
    }
