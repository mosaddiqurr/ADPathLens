from fastapi.testclient import TestClient

from tests.test_imports import authenticated_project


def import_small_demo(client: TestClient, project_id: str, csrf: str) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/datasets/import-demo",
        headers={"X-CSRF-Token": csrf},
        json={"demo": "small", "authorization_confirmed": True},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def find_node(client: TestClient, snapshot_id: str, name: str) -> dict[str, object]:
    response = client.get(
        f"/api/v1/snapshots/{snapshot_id}/nodes",
        params={"search": name, "page_size": 10},
    )
    assert response.status_code == 200
    return next(node for node in response.json()["items"] if node["display_name"] == name)


def test_graph_summary_and_explainable_bounded_paths(client: TestClient) -> None:
    project_id, csrf = authenticated_project(client)
    snapshot_id = import_small_demo(client, project_id, csrf)
    summary = client.get(f"/api/v1/snapshots/{snapshot_id}/graph/summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["node_count"] == 35
    assert summary.json()["relationship_count"] >= 55
    assert summary.json()["high_value_count"] >= 5

    mina = find_node(client, snapshot_id, "Mina Rahman")
    domain_admins = find_node(client, snapshot_id, "Domain Admins")
    analysis = client.post(
        f"/api/v1/snapshots/{snapshot_id}/analyses",
        headers={"X-CSRF-Token": csrf},
        json={
            "start_node_id": mina["id"],
            "target_node_id": domain_admins["id"],
            "target_kind": "specific",
            "algorithm": "shortest_hops",
            "maximum_depth": 12,
            "maximum_paths": 5,
            "minimum_confidence": "low",
        },
    )
    assert analysis.status_code == 201, analysis.text
    result = analysis.json()
    assert result["status"] == "complete"
    assert result["path_count"] == 1
    assert result["paths"][0]["hop_count"] >= 1
    assert result["paths"][0]["steps"][0]["source_name"] == "Mina Rahman"
    assert result["paths"][0]["steps"][-1]["target_name"] == "Domain Admins"
    assert "does not prove" in result["paths"][0]["limitations"]
    assert all(step["relationship_id"] for step in result["paths"][0]["steps"])
    assert client.get(f"/api/v1/analyses/{result['id']}").json() == result

    bounded = client.post(
        f"/api/v1/snapshots/{snapshot_id}/analyses",
        headers={"X-CSRF-Token": csrf},
        json={
            "start_node_id": mina["id"],
            "target_node_id": domain_admins["id"],
            "target_kind": "specific",
            "algorithm": "shortest_hops",
            "maximum_depth": 2,
            "maximum_paths": 5,
        },
    )
    assert bounded.status_code == 201
    assert bounded.json()["path_count"] == 0


def test_graph_endpoint_is_bounded_and_node_changes_invalidate_cache(client: TestClient) -> None:
    project_id, csrf = authenticated_project(client)
    snapshot_id = import_small_demo(client, project_id, csrf)
    mina = find_node(client, snapshot_id, "Mina Rahman")
    graph = client.get(
        f"/api/v1/snapshots/{snapshot_id}/graph",
        params={"focus_node_id": mina["id"], "depth": 1, "maximum_nodes": 10},
    )
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) <= 10
    updated = client.patch(
        f"/api/v1/nodes/{mina['id']}",
        headers={"X-CSRF-Token": csrf},
        json={"high_value": True},
    )
    assert updated.status_code == 200
    assert updated.json()["high_value"] is True
    summary = client.get(f"/api/v1/snapshots/{snapshot_id}/graph/summary").json()
    assert summary["high_value_count"] >= 6
