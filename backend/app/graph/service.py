from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.graph.catalog import RELATIONSHIP_CATALOG
from app.models.entities import (
    DirectoryNode,
    DirectoryRelationship,
    GraphSnapshot,
    RiskRuleConfiguration,
)


@dataclass
class CacheEntry:
    revision: int
    expires_at: float
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]]


class GraphCache:
    def __init__(self, maximum_entries: int = 12) -> None:
        self.maximum_entries = maximum_entries
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()

    def get(self, snapshot_id: str, revision: int) -> nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]] | None:
        entry = self._entries.get(snapshot_id)
        if not entry or entry.revision != revision or entry.expires_at < time.monotonic():
            self._entries.pop(snapshot_id, None)
            return None
        self._entries.move_to_end(snapshot_id)
        return entry.graph

    def put(
        self,
        snapshot_id: str,
        revision: int,
        graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]],
    ) -> None:
        self._entries[snapshot_id] = CacheEntry(
            revision=revision,
            expires_at=time.monotonic() + get_settings().graph_cache_ttl_seconds,
            graph=graph,
        )
        self._entries.move_to_end(snapshot_id)
        while len(self._entries) > self.maximum_entries:
            self._entries.popitem(last=False)

    def invalidate(self, snapshot_id: str) -> None:
        self._entries.pop(snapshot_id, None)

    def clear(self) -> None:
        self._entries.clear()


graph_cache = GraphCache()


async def build_graph(db: AsyncSession, snapshot_id: str) -> nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]]:
    snapshot = await db.get(GraphSnapshot, snapshot_id)
    if not snapshot:
        raise AppError(404, "Snapshot not found", "The snapshot does not exist.", code="not_found")
    cached = graph_cache.get(snapshot.id, snapshot.revision)
    if cached is not None:
        return cached
    nodes = list((await db.scalars(select(DirectoryNode).where(DirectoryNode.snapshot_id == snapshot.id))).all())
    relationships = list(
        (await db.scalars(select(DirectoryRelationship).where(DirectoryRelationship.snapshot_id == snapshot.id))).all()
    )
    configurations = list(
        (await db.scalars(select(RiskRuleConfiguration).order_by(RiskRuleConfiguration.created_at))).all()
    )
    configured_weights: dict[str, float] = {}
    for configuration in configurations:
        raw_weights = configuration.configuration_json.get("relationship_weights", {})
        if isinstance(raw_weights, dict):
            for relationship_type, value in raw_weights.items():
                if relationship_type in RELATIONSHIP_CATALOG and isinstance(value, int | float):
                    configured_weights[relationship_type] = float(value)
    settings = get_settings()
    if len(nodes) > settings.max_graph_nodes or len(relationships) > settings.max_graph_relationships:
        raise AppError(
            413,
            "Graph too large",
            "This snapshot exceeds the configured graph-analysis limits.",
            code="graph_too_large",
        )
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]] = nx.MultiDiGraph(
        snapshot_id=snapshot.id, revision=snapshot.revision
    )
    for node in nodes:
        graph.add_node(
            node.id,
            id=node.id,
            external_id=node.external_id,
            type=node.node_type,
            name=node.name,
            display_name=node.display_name,
            domain=node.domain_name,
            enabled=node.enabled,
            privileged=node.privileged,
            high_value=node.high_value,
            risk_level=node.risk_level,
            metadata=node.metadata_json,
        )
    confidence_multiplier = {"high": 1.0, "medium": 1.25, "low": 1.75, "unknown": 2.0}
    for relationship in relationships:
        definition = RELATIONSHIP_CATALOG[relationship.relationship_type]
        edge_data: dict[str, Any] = {
            "id": relationship.id,
            "relationship_id": relationship.id,
            "external_id": relationship.external_id,
            "type": relationship.relationship_type,
            "direction": relationship.direction,
            "active": relationship.active,
            "inherited": relationship.inherited,
            "confidence": relationship.confidence,
            "risk_weight": configured_weights.get(relationship.relationship_type, relationship.risk_weight),
            "effective_cost": configured_weights.get(relationship.relationship_type, relationship.risk_weight)
            * confidence_multiplier[relationship.confidence]
            * (1.15 if relationship.inherited else 1.0),
            "path_eligible": definition.path_eligible,
            "description": relationship.description,
            "evidence": relationship.evidence_json,
            "remediation": definition.remediation,
        }
        graph.add_edge(
            relationship.source_node_id,
            relationship.target_node_id,
            key=relationship.id,
            **edge_data,
        )
        if definition.direction == "bidirectional":
            graph.add_edge(
                relationship.target_node_id,
                relationship.source_node_id,
                key=f"{relationship.id}:reverse",
                **edge_data,
                traversed_reverse=True,
            )
    graph_cache.put(snapshot.id, snapshot.revision, graph)
    return graph
