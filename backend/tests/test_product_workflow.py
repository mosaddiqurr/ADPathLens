from fastapi.testclient import TestClient

from tests.test_graph_analysis import find_node, import_small_demo
from tests.test_imports import authenticated_project


def test_latest_analysis_and_branded_reports_preserve_evidence(client: TestClient) -> None:
    project, csrf = authenticated_project(client)
    snapshot = import_small_demo(client, project, csrf)
    latest_url = f"/api/v1/snapshots/{snapshot}/analyses/latest"
    assert client.get(latest_url).json() is None
    mina = find_node(client, snapshot, "Mina Rahman")
    target = find_node(client, snapshot, "Domain Admins")
    headers = {"X-CSRF-Token": csrf}
    payload = {
        "start_node_id": mina["id"],
        "target_node_id": target["id"],
        "algorithm": "top_paths",
        "maximum_depth": 12,
        "maximum_paths": 5,
    }
    first = client.post(f"/api/v1/snapshots/{snapshot}/analyses", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    second = client.post(f"/api/v1/snapshots/{snapshot}/analyses", headers=headers, json=payload)
    assert second.status_code == 201
    restored = client.get(latest_url).json()
    assert restored == second.json()
    assert restored["request_parameters"]["maximum_depth"] == 12
    assert restored["path_count"] == len(restored["paths"])
    client.post(f"/api/v1/snapshots/{snapshot}/risk-scan", headers=headers)
    later_response = client.post(
        f"/api/v1/projects/{project}/datasets/import-demo",
        headers=headers,
        json={"demo": "after", "authorization_confirmed": True},
    )
    assert later_response.status_code == 201
    later = later_response.json()["id"]
    client.post(f"/api/v1/snapshots/{later}/risk-scan", headers=headers)
    scoped = client.get(
        f"/api/v1/projects/{project}/findings", params={"snapshot_id": snapshot, "page_size": 100}
    ).json()
    assert scoped["total"] > 0
    assert all(item["snapshot_id"] == snapshot for item in scoped["items"])
    for format in ("html", "pdf", "json", "csv"):
        report = client.post(
            f"/api/v1/projects/{project}/reports",
            headers=headers,
            json={"snapshot_id": snapshot, "report_type": "executive", "format": format},
        )
        assert report.status_code == 201, report.text
        download = client.get(f"/api/v1/reports/{report.json()['id']}/download")
        assert download.status_code == 200
        if format == "html":
            assert "data:image/png;base64," in download.text
            assert "Priority fixes" in download.text
            assert "Mina Rahman" in download.text
            assert "Technical provenance" in download.text
        if format == "pdf":
            assert download.content.startswith(b"%PDF")
        if format == "json":
            source = download.json()["source"]
            assert source["path_count"] == restored["path_count"]
            assert source["important_paths"]
            assert source["priority_fixes"]
            assert source["analysis_id"] == restored["id"]
            assert source["important_paths"][0]["severity"] in {"critical", "high", "medium", "low"}
            assert source["important_paths"][0]["relationships"][0]["evidence"]["fictional"] is True
    selected = client.post(
        f"/api/v1/projects/{project}/reports",
        headers=headers,
        json={
            "snapshot_id": snapshot,
            "analysis_id": first.json()["id"],
            "report_type": "executive",
            "format": "json",
        },
    )
    assert selected.status_code == 201
    selected_source = client.get(f"/api/v1/reports/{selected.json()['id']}/download").json()["source"]
    assert selected_source["analysis_id"] == first.json()["id"]
    assert selected_source["path_scope"].startswith("Selected completed analysis")
    mismatched = client.post(
        f"/api/v1/projects/{project}/reports",
        headers=headers,
        json={
            "snapshot_id": later,
            "analysis_id": first.json()["id"],
            "report_type": "executive",
            "format": "json",
        },
    )
    assert mismatched.status_code == 422
    assert "Analysis mismatch" in mismatched.text
    client.post("/api/v1/auth/logout", headers=headers)
    assert client.get(latest_url).status_code == 401
