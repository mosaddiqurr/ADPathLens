import json
from pathlib import Path
from typing import Any

import networkx as nx
import pytest

from app.analysis.pathfinding import find_paths
from app.api.v1.routers.analysis import _reverse_paths
from app.core.config import get_settings
from app.data.demos import small_demo
from app.importers.validator import validate_json_bytes
from app.schemas.graph import AnalysisRequest
from tests.test_imports import small_json_dataset


def test_reverse_filters_disabled_sources_and_prioritizes_before_cap() -> None:
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]] = nx.MultiDiGraph()
    graph.add_node("target", type="Group", enabled=True, privileged=True, display_name="Target")
    for name, node_type, enabled, cost in (
        ("A expensive", "User", True, 10),
        ("Z critical", "User", True, 1),
        ("Computer", "Computer", True, 2),
        ("Disabled", "User", False, 2),
    ):
        graph.add_node(name, type=node_type, enabled=enabled, privileged=False, display_name=name)
        graph.add_edge(
            name,
            "target",
            relationship_id=name,
            type="MemberOf",
            active=True,
            path_eligible=True,
            confidence="high",
            effective_cost=cost,
        )
    payload = AnalysisRequest(
        start_node_id="Computer",
        target_node_id="target",
        algorithm="reverse_reachability",
        source_node_types=["User"],
        maximum_paths=1,
    )
    paths, truncated = _reverse_paths(graph, "target", payload)
    assert paths[0].nodes == ("Z critical", "target") and truncated
    payload.maximum_paths = 25
    assert {p.nodes[0] for p in _reverse_paths(graph, "target", payload)[0]} == {"A expensive", "Z critical"}
    payload.include_disabled = True
    assert {p.nodes[0] for p in _reverse_paths(graph, "target", payload)[0]} == {
        "A expensive",
        "Z critical",
        "Disabled",
    }


@pytest.mark.parametrize("algorithm", ["shortest_hops", "lowest_cost", "top_paths"])
def test_cycles_and_edge_direction_never_fabricate_a_route(algorithm: str) -> None:
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]] = nx.MultiDiGraph()
    graph.add_nodes_from(["a", "b", "target"])
    for source, target in [("a", "b"), ("b", "a"), ("b", "target")]:
        graph.add_edge(
            source,
            target,
            relationship_id=f"{source}-{target}",
            type="MemberOf",
            active=True,
            path_eligible=True,
            confidence="high",
            effective_cost=3,
        )
    kwargs = {"algorithm": algorithm, "maximum_depth": 12, "maximum_paths": 25}
    paths, _ = find_paths(graph, "a", {"target"}, **kwargs)
    assert [p.nodes for p in paths] == [("a", "b", "target")]
    assert paths[0].edges == ("a-b", "b-target")
    assert not find_paths(graph, "target", {"a"}, **kwargs)[0]


def test_missing_and_duplicate_relationships_are_rejected() -> None:
    data = json.loads(small_json_dataset())
    data["relationships"].append({**data["relationships"][0], "id": "duplicate"})
    result = validate_json_bytes(json.dumps(data).encode(), get_settings())
    assert not result.valid and any(m.code == "duplicate_relationship" for m in result.messages)
    data["relationships"] = [{**data["relationships"][0], "target": "missing"}]
    result = validate_json_bytes(json.dumps(data).encode(), get_settings())
    assert not result.valid and any(m.code == "missing_endpoint" for m in result.messages)


def test_extreme_nesting_is_a_validation_error() -> None:
    result = validate_json_bytes(b"[" * 2000 + b"0" + b"]" * 2000, get_settings())
    assert not result.valid and result.messages[0].code == "json_too_deep"


def test_public_demo_is_the_packaged_backend_fixture() -> None:
    demo_path = Path(__file__).resolve().parents[2] / "frontend" / "public" / "northbridge-demo.json"
    assert json.loads(demo_path.read_text(encoding="utf-8")) == small_demo()
