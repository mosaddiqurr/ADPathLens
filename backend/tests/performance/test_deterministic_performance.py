from __future__ import annotations

import json
import time
import tracemalloc
from typing import Any

import networkx as nx
from fastapi.testclient import TestClient

from app.analysis.pathfinding import find_paths
from tests.test_imports import authenticated_project


def _bounded_graph(node_count: int) -> nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]]:
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]] = nx.MultiDiGraph()
    for index in range(node_count):
        graph.add_node(
            f"node-{index:05}",
            external_id=f"synthetic-{index:05}",
            display_name=f"Synthetic Node {index:05}",
            enabled=True,
        )
    for index in range(node_count - 1):
        graph.add_edge(
            f"node-{index:05}",
            f"node-{index + 1:05}",
            key=f"chain-{index:05}",
            relationship_id=f"chain-{index:05}",
            type="MemberOf",
            active=True,
            path_eligible=True,
            confidence="high",
            effective_cost=3.0,
            remediation="Review fictional membership.",
            evidence={"fictional": True},
        )
    for index in range(node_count * 2):
        source = index % node_count
        target = (source + 97 + (index // node_count)) % node_count
        if source == target:
            continue
        graph.add_edge(
            f"node-{source:05}",
            f"node-{target:05}",
            key=f"context-{index:06}",
            relationship_id=f"context-{index:06}",
            type="ConnectedTo",
            active=True,
            path_eligible=False,
            confidence="medium",
            effective_cost=5.0,
            remediation="Context only.",
            evidence={"fictional": True},
        )
    return graph


def test_bounded_graph_performance_is_deterministic() -> None:
    measurements: list[dict[str, int | float]] = []
    for node_count in (1_000, 5_000, 10_000):
        tracemalloc.start()
        started = time.perf_counter()
        graph = _bounded_graph(node_count)
        build_seconds = time.perf_counter() - started
        query_started = time.perf_counter()
        paths, truncated = find_paths(
            graph,
            "node-00000",
            {"node-00008"},
            algorithm="shortest_hops",
            maximum_depth=12,
            maximum_paths=5,
            deadline_seconds=5.0,
            maximum_expansions=20_000,
        )
        query_seconds = time.perf_counter() - query_started
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert paths
        assert paths[0].edges == tuple(f"chain-{index:05}" for index in range(8))
        assert truncated is False
        assert build_seconds < 30
        assert query_seconds < 5
        assert peak_bytes < 500 * 1024 * 1024
        measurements.append(
            {
                "nodes": node_count,
                "edges": graph.number_of_edges(),
                "build_seconds": round(build_seconds, 4),
                "path_seconds": round(query_seconds, 4),
                "peak_memory_mib": round(peak_bytes / 1024 / 1024, 2),
            }
        )
    print("PERFORMANCE_GRAPH=" + json.dumps(measurements, sort_keys=True))


def test_medium_application_workflow_performance(client: TestClient) -> None:
    project_id, csrf = authenticated_project(client)
    import_started = time.perf_counter()
    imported = client.post(
        f"/api/v1/projects/{project_id}/datasets/import-demo",
        headers={"X-CSRF-Token": csrf},
        json={"demo": "medium", "authorization_confirmed": True},
    )
    import_seconds = time.perf_counter() - import_started
    assert imported.status_code == 201, imported.text
    snapshot_id = imported.json()["id"]

    search_started = time.perf_counter()
    search = client.get(
        f"/api/v1/snapshots/{snapshot_id}/search",
        params={"query": "Synthetic User 0464"},
    )
    search_seconds = time.perf_counter() - search_started
    assert search.status_code == 200
    assert search.json()[0]["display_name"] == "Synthetic User 0464"

    summary = client.get(f"/api/v1/snapshots/{snapshot_id}/graph/summary")
    assert summary.status_code == 200
    assert summary.json()["node_count"] == 500
    assert summary.json()["relationship_count"] == 1_501
    assert import_seconds < 30
    assert search_seconds < 5

    before = client.post(
        f"/api/v1/projects/{project_id}/datasets/import-demo",
        headers={"X-CSRF-Token": csrf},
        json={"demo": "before", "authorization_confirmed": True},
    )
    after = client.post(
        f"/api/v1/projects/{project_id}/datasets/import-demo",
        headers={"X-CSRF-Token": csrf},
        json={"demo": "after", "authorization_confirmed": True},
    )
    assert before.status_code == 201
    assert after.status_code == 201
    comparison_started = time.perf_counter()
    comparison = client.post(
        f"/api/v1/projects/{project_id}/comparisons",
        headers={"X-CSRF-Token": csrf},
        json={
            "before_snapshot_id": before.json()["id"],
            "after_snapshot_id": after.json()["id"],
        },
    )
    comparison_seconds = time.perf_counter() - comparison_started
    assert comparison.status_code == 201
    assert comparison.json()["relationships_removed"] == 5

    report_started = time.perf_counter()
    report = client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers={"X-CSRF-Token": csrf},
        json={
            "snapshot_id": after.json()["id"],
            "report_type": "findings",
            "format": "json",
        },
    )
    report_seconds = time.perf_counter() - report_started
    assert report.status_code == 201
    assert comparison_seconds < 5
    assert report_seconds < 5
    print(
        "PERFORMANCE_APPLICATION="
        + json.dumps(
            {
                "nodes": 500,
                "edges": 1_501,
                "import_seconds": round(import_seconds, 4),
                "search_seconds": round(search_seconds, 4),
                "comparison_seconds": round(comparison_seconds, 4),
                "report_seconds": round(report_seconds, 4),
            },
            sort_keys=True,
        )
    )
