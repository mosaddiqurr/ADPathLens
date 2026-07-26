from collections import Counter
from typing import Annotated, Any

import networkx as nx
from fastapi import APIRouter, Query, Request
from sqlalchemy import func, or_, select

from app.api.deps import DB, CurrentUser, EditorCsrf
from app.audit.service import record_audit
from app.core.errors import AppError
from app.graph.catalog import serialize_catalog
from app.graph.service import build_graph, graph_cache
from app.models.entities import DirectoryNode, DirectoryRelationship
from app.schemas.graph import (
    GraphSummaryResponse,
    NodeResponse,
    NodeUpdate,
    PageResponse,
    RelationshipResponse,
    RelationshipUpdate,
)
from app.services.authorization import snapshot_or_404

router = APIRouter(tags=["graph"])


@router.get("/graph/catalog")
async def relationship_catalog(_: CurrentUser) -> dict[str, dict[str, object]]:
    return serialize_catalog()


@router.get("/snapshots/{snapshot_id}/graph/summary", response_model=GraphSummaryResponse)
async def graph_summary(snapshot_id: str, db: DB, user: CurrentUser) -> GraphSummaryResponse:
    await snapshot_or_404(db, user, snapshot_id)
    graph = await build_graph(db, snapshot_id)
    node_types = Counter(str(data["type"]) for _, data in graph.nodes(data=True))
    relationship_types = Counter(
        str(data["type"]) for _, _, data in graph.edges(data=True) if not data.get("traversed_reverse")
    )
    return GraphSummaryResponse(
        snapshot_id=snapshot_id,
        node_count=graph.number_of_nodes(),
        relationship_count=sum(relationship_types.values()),
        high_value_count=sum(bool(data["high_value"]) for _, data in graph.nodes(data=True)),
        privileged_count=sum(bool(data["privileged"]) for _, data in graph.nodes(data=True)),
        nodes_by_type=dict(sorted(node_types.items())),
        relationships_by_type=dict(sorted(relationship_types.items())),
    )


@router.get("/snapshots/{snapshot_id}/graph")
async def graph_elements(
    snapshot_id: str,
    db: DB,
    user: CurrentUser,
    focus_node_id: str | None = None,
    depth: Annotated[int, Query(ge=1, le=3)] = 1,
    node_types: str = "",
    relationship_types: str = "",
    maximum_nodes: Annotated[int, Query(ge=1, le=2000)] = 500,
    maximum_relationships: Annotated[int, Query(ge=1, le=5000)] = 1500,
) -> dict[str, Any]:
    await snapshot_or_404(db, user, snapshot_id)
    graph = await build_graph(db, snapshot_id)
    selected_nodes: set[str]
    if focus_node_id:
        if focus_node_id not in graph:
            raise AppError(404, "Node not found", "The focus node does not exist.", code="not_found")
        undirected = graph.to_undirected(as_view=True)
        selected_nodes = set(nx.single_source_shortest_path_length(undirected, focus_node_id, cutoff=depth))
    else:
        selected_nodes = set(graph.nodes)
    allowed_node_types = {item for item in node_types.split(",") if item}
    if allowed_node_types:
        selected_nodes = {node for node in selected_nodes if graph.nodes[node]["type"] in allowed_node_types}
    ordered_nodes = sorted(
        selected_nodes,
        key=lambda node: (
            not bool(graph.nodes[node]["high_value"]),
            str(graph.nodes[node]["type"]),
            str(graph.nodes[node]["display_name"]).lower(),
            node,
        ),
    )
    truncated = len(ordered_nodes) > maximum_nodes
    ordered_nodes = ordered_nodes[:maximum_nodes]
    selected = set(ordered_nodes)
    allowed_relationships = {item for item in relationship_types.split(",") if item}
    edge_items: list[tuple[str, str, dict[str, Any]]] = []
    seen_relationships: set[str] = set()
    for source, target, data in graph.edges(data=True):
        relationship_id = str(data["relationship_id"])
        if (
            source not in selected
            or target not in selected
            or relationship_id in seen_relationships
            or (allowed_relationships and data["type"] not in allowed_relationships)
        ):
            continue
        seen_relationships.add(relationship_id)
        edge_items.append((source, target, data))
    edge_items.sort(key=lambda item: (item[2]["type"], item[2]["external_id"]))
    if len(edge_items) > maximum_relationships:
        truncated = True
        edge_items = edge_items[:maximum_relationships]
    return {
        "snapshot_id": snapshot_id,
        "truncated": truncated,
        "limits": {"nodes": maximum_nodes, "relationships": maximum_relationships},
        "nodes": [
            {"data": {**graph.nodes[node], "label": graph.nodes[node]["display_name"]}} for node in ordered_nodes
        ],
        "relationships": [
            {
                "data": {
                    **data,
                    "id": data["relationship_id"],
                    "source": source,
                    "target": target,
                    "label": data["type"],
                }
            }
            for source, target, data in edge_items
        ],
    }


@router.get("/snapshots/{snapshot_id}/nodes", response_model=PageResponse)
async def list_nodes(
    snapshot_id: str,
    db: DB,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    search: str = "",
    node_type: str = "",
    high_value: bool | None = None,
) -> PageResponse:
    await snapshot_or_404(db, user, snapshot_id)
    conditions = [DirectoryNode.snapshot_id == snapshot_id]
    if search:
        term = f"%{search[:256]}%"
        conditions.append(
            or_(
                DirectoryNode.name.ilike(term),
                DirectoryNode.display_name.ilike(term),
                DirectoryNode.external_id.ilike(term),
                DirectoryNode.domain_name.ilike(term),
            )
        )
    if node_type:
        conditions.append(DirectoryNode.node_type == node_type)
    if high_value is not None:
        conditions.append(DirectoryNode.high_value == high_value)
    total = await db.scalar(select(func.count(DirectoryNode.id)).where(*conditions)) or 0
    items = list(
        (
            await db.scalars(
                select(DirectoryNode)
                .where(*conditions)
                .order_by(DirectoryNode.display_name, DirectoryNode.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return PageResponse(
        items=[NodeResponse.model_validate(item).model_dump() for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/snapshots/{snapshot_id}/relationships", response_model=PageResponse)
async def list_relationships(
    snapshot_id: str,
    db: DB,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    relationship_type: str = "",
    confidence: str = "",
) -> PageResponse:
    await snapshot_or_404(db, user, snapshot_id)
    conditions = [DirectoryRelationship.snapshot_id == snapshot_id]
    if relationship_type:
        conditions.append(DirectoryRelationship.relationship_type == relationship_type)
    if confidence:
        conditions.append(DirectoryRelationship.confidence == confidence)
    total = await db.scalar(select(func.count(DirectoryRelationship.id)).where(*conditions)) or 0
    items = list(
        (
            await db.scalars(
                select(DirectoryRelationship)
                .where(*conditions)
                .order_by(DirectoryRelationship.relationship_type, DirectoryRelationship.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return PageResponse(
        items=[RelationshipResponse.model_validate(item).model_dump() for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/nodes/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str, db: DB, user: CurrentUser) -> DirectoryNode:
    node = await db.get(DirectoryNode, node_id)
    if not node:
        raise AppError(404, "Node not found", "The node does not exist.", code="not_found")
    await snapshot_or_404(db, user, node.snapshot_id)
    return node


@router.patch("/nodes/{node_id}", response_model=NodeResponse)
async def update_node(node_id: str, payload: NodeUpdate, request: Request, db: DB, user: EditorCsrf) -> DirectoryNode:
    node = await db.get(DirectoryNode, node_id)
    if not node:
        raise AppError(404, "Node not found", "The node does not exist.", code="not_found")
    snapshot = await snapshot_or_404(db, user, node.snapshot_id, minimum_role="analyst")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(node, key, value)
    snapshot.revision += 1
    graph_cache.invalidate(snapshot.id)
    await record_audit(db, request, "node.updated", "node", "Directory node updated", user=user, entity_id=node.id)
    await db.commit()
    await db.refresh(node)
    return node


@router.get("/relationships/{relationship_id}", response_model=RelationshipResponse)
async def get_relationship(relationship_id: str, db: DB, user: CurrentUser) -> DirectoryRelationship:
    relationship = await db.get(DirectoryRelationship, relationship_id)
    if not relationship:
        raise AppError(404, "Relationship not found", "The relationship does not exist.", code="not_found")
    await snapshot_or_404(db, user, relationship.snapshot_id)
    return relationship


@router.patch("/relationships/{relationship_id}", response_model=RelationshipResponse)
async def update_relationship(
    relationship_id: str,
    payload: RelationshipUpdate,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> DirectoryRelationship:
    relationship = await db.get(DirectoryRelationship, relationship_id)
    if not relationship:
        raise AppError(404, "Relationship not found", "The relationship does not exist.", code="not_found")
    snapshot = await snapshot_or_404(db, user, relationship.snapshot_id, minimum_role="analyst")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(relationship, key, value)
    snapshot.revision += 1
    graph_cache.invalidate(snapshot.id)
    await record_audit(
        db,
        request,
        "relationship.updated",
        "relationship",
        "Directory relationship updated",
        user=user,
        entity_id=relationship.id,
    )
    await db.commit()
    await db.refresh(relationship)
    return relationship


@router.get("/snapshots/{snapshot_id}/search", response_model=list[NodeResponse])
async def search_nodes(
    snapshot_id: str,
    query: str,
    db: DB,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[DirectoryNode]:
    await snapshot_or_404(db, user, snapshot_id)
    term = f"%{query[:256]}%"
    return list(
        (
            await db.scalars(
                select(DirectoryNode)
                .where(
                    DirectoryNode.snapshot_id == snapshot_id,
                    or_(
                        DirectoryNode.name.ilike(term),
                        DirectoryNode.display_name.ilike(term),
                        DirectoryNode.external_id.ilike(term),
                    ),
                )
                .order_by(DirectoryNode.high_value.desc(), DirectoryNode.display_name)
                .limit(limit)
            )
        ).all()
    )


@router.get("/snapshots/{snapshot_id}/high-value-assets", response_model=list[NodeResponse])
async def high_value_assets(snapshot_id: str, db: DB, user: CurrentUser) -> list[DirectoryNode]:
    await snapshot_or_404(db, user, snapshot_id)
    return list(
        (
            await db.scalars(
                select(DirectoryNode)
                .where(
                    DirectoryNode.snapshot_id == snapshot_id,
                    DirectoryNode.high_value.is_(True),
                )
                .order_by(DirectoryNode.display_name)
            )
        ).all()
    )
