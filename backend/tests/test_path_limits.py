from typing import Any

import networkx as nx
import pytest

from app.analysis.pathfinding import find_paths
from app.api.v1.routers.analysis import _reverse_paths
from app.core.config import get_settings
from app.schemas.graph import AnalysisRequest


def test_excluding_all_relationships_and_disabled_sources_is_respected() -> None:
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]] = nx.MultiDiGraph()
    graph.add_node("start", enabled=False)
    graph.add_node("target", enabled=True)
    graph.add_edge(
        "start",
        "target",
        relationship_id="edge",
        type="MemberOf",
        active=True,
        path_eligible=True,
        confidence="high",
        effective_cost=3.0,
    )
    arguments = {"algorithm": "top_paths", "maximum_depth": 12, "maximum_paths": 25}
    assert not find_paths(graph, "start", {"target"}, **arguments)[0]
    assert not find_paths(graph, "start", {"target"}, include_disabled=True, relationship_types=set(), **arguments)[0]
    assert find_paths(graph, "start", {"target"}, include_disabled=True, **arguments)[0]


def test_path_cap_reports_partial_results_with_alternative_routes() -> None:
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]] = nx.MultiDiGraph()
    for node in ("start", "target", "other"):
        graph.add_node(node, enabled=True)
    for source, target in (("start", "target"), ("start", "other"), ("other", "target")):
        graph.add_edge(
            source,
            target,
            relationship_id=f"{source}-{target}",
            type="MemberOf",
            active=True,
            path_eligible=True,
            confidence="high",
            effective_cost=3.0,
        )
    paths, truncated = find_paths(graph, "start", {"target"}, algorithm="top_paths", maximum_depth=12, maximum_paths=1)
    assert len(paths) == 1 and truncated


def test_reverse_reachability_shares_its_work_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]] = nx.MultiDiGraph()
    graph.add_node("target", privileged=True, enabled=True, display_name="Target")
    for index in range(10):
        source = f"source-{index}"
        graph.add_node(source, privileged=False, enabled=True, display_name=source)
        graph.add_edge(
            source,
            "target",
            relationship_id=source,
            type="MemberOf",
            active=True,
            path_eligible=True,
            confidence="high",
            effective_cost=3.0,
        )
    monkeypatch.setattr(get_settings(), "max_analysis_expansions", 3)
    paths, truncated = _reverse_paths(
        graph,
        "target",
        AnalysisRequest(
            start_node_id="source-0", target_node_id="target", algorithm="reverse_reachability", maximum_paths=25
        ),
    )
    assert len(paths) <= 3 and truncated
