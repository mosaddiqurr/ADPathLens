from __future__ import annotations

import hashlib
import heapq
import time
from dataclasses import dataclass
from typing import Any

import networkx as nx


@dataclass(frozen=True)
class PathResult:
    nodes: tuple[str, ...]
    edges: tuple[str, ...]
    total_weight: float
    confidence: str

    @property
    def signature(self) -> str:
        return hashlib.sha256("|".join((*self.nodes, *self.edges)).encode()).hexdigest()


def find_paths(
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]],
    start: str,
    targets: set[str],
    *,
    algorithm: str,
    maximum_depth: int,
    maximum_paths: int,
    relationship_types: set[str] | None = None,
    minimum_confidence: str = "low",
    include_disabled: bool = False,
    deadline_seconds: float = 5.0,
    maximum_expansions: int = 100_000,
    reverse: bool = False,
) -> tuple[list[PathResult], bool]:
    if start not in graph:
        return [], False
    confidence_rank = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
    minimum_rank = confidence_rank[minimum_confidence]
    working = graph.reverse(copy=False) if reverse else graph
    started = time.monotonic()
    queue: list[tuple[float, int, tuple[str, ...], tuple[str, ...], float, str]] = [(0.0, 0, (start,), (), 0.0, "high")]
    results: list[PathResult] = []
    expansions = 0
    truncated = False
    while queue and len(results) < maximum_paths:
        if expansions >= maximum_expansions or time.monotonic() - started > deadline_seconds:
            truncated = True
            break
        priority, hops, nodes, edges, total_cost, path_confidence = heapq.heappop(queue)
        current = nodes[-1]
        if current in targets and hops > 0:
            results.append(PathResult(nodes, edges, total_cost, path_confidence))
            if algorithm in {"shortest_hops", "lowest_cost"}:
                break
            continue
        if hops >= maximum_depth:
            continue
        outgoing: list[tuple[str, str, dict[str, Any]]] = []
        for _, target, key, data in working.out_edges(current, keys=True, data=True):
            outgoing.append((target, str(key), data))
        outgoing.sort(
            key=lambda item: (
                float(item[2]["effective_cost"]),
                str(working.nodes[item[0]].get("external_id", "")),
                item[1],
            )
        )
        for target, _, data in outgoing:
            expansions += 1
            if target in nodes or not data["active"] or not data["path_eligible"]:
                continue
            if relationship_types and data["type"] not in relationship_types:
                continue
            if confidence_rank[data["confidence"]] < minimum_rank:
                continue
            if not include_disabled and not working.nodes[target].get("enabled", True):
                continue
            next_nodes = (*nodes, target)
            next_edges = (*edges, data["relationship_id"])
            next_cost = total_cost + float(data["effective_cost"])
            confidence = min(
                (path_confidence, data["confidence"]),
                key=lambda value: confidence_rank[value],
            )
            next_hops = hops + 1
            next_priority = float(next_hops) if algorithm == "shortest_hops" else next_cost
            heapq.heappush(
                queue,
                (next_priority, next_hops, next_nodes, next_edges, next_cost, confidence),
            )
    results.sort(key=lambda path: (path.total_weight, len(path.edges), path.nodes, path.edges))
    if algorithm == "shortest_hops":
        results.sort(key=lambda path: (len(path.edges), path.total_weight, path.nodes, path.edges))
    return results[:maximum_paths], truncated


def explain_path(
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]], path: PathResult
) -> tuple[str, list[dict[str, Any]]]:
    steps: list[dict[str, Any]] = []
    for position, relationship_id in enumerate(path.edges):
        source = path.nodes[position]
        target = path.nodes[position + 1]
        matching = [data for _, _, data in graph.edges(source, data=True) if data["relationship_id"] == relationship_id]
        data = matching[0]
        source_name = graph.nodes[source]["display_name"]
        target_name = graph.nodes[target]["display_name"]
        explanation = (
            f"{source_name} has {data['type']} to {target_name}. "
            "This security-relevant relationship may contribute to a possible control path "
            "and requires validation."
        )
        steps.append(
            {
                "position": position + 1,
                "source_node_id": source,
                "relationship_id": relationship_id,
                "target_node_id": target,
                "explanation": explanation,
                "remediation": data["remediation"],
                "confidence": data["confidence"],
                "risk_weight": data["effective_cost"],
                "evidence": data["evidence"],
            }
        )
    summary = (
        f"Possible privilege path with {len(path.edges)} hops. Imported relationships suggest "
        "a potential route toward greater privilege; this is not proof of compromise."
    )
    return summary, steps
