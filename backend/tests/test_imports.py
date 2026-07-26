import io
import json
import zipfile

from fastapi.testclient import TestClient


def authenticated_project(client: TestClient) -> tuple[str, str]:
    setup = client.post(
        "/api/v1/auth/setup",
        json={
            "email": "admin@example.com",
            "display_name": "Test Administrator",
            "password": "Correct-Horse-Battery-Staple-123",
            "authorization_confirmed": True,
        },
    )
    assert setup.status_code == 201, setup.text
    csrf = setup.json()["csrf_token"]
    workspace_id = client.get("/api/v1/workspaces").json()[0]["id"]
    project = client.post(
        "/api/v1/projects",
        headers={"X-CSRF-Token": csrf},
        json={"workspace_id": workspace_id, "name": "Synthetic Test Project"},
    )
    return project.json()["id"], csrf


def small_json_dataset(*, unknown: bool = False) -> bytes:
    payload = {
        "metadata": {"name": "Test", "version": "1.0"},
        "nodes": [
            {
                "id": "start",
                "type": "Unknown" if unknown else "User",
                "name": "Synthetic Start",
            },
            {
                "id": "target",
                "type": "Group",
                "name": "Synthetic Target",
                "high_value": True,
                "privileged": True,
            },
        ],
        "relationships": [
            {
                "id": "edge-1",
                "source": "start",
                "target": "target",
                "type": "GenericAll",
                "confidence": "high",
            }
        ],
    }
    return json.dumps(payload).encode()


def test_demo_and_json_import_are_transactional_and_deduplicated(client: TestClient) -> None:
    project_id, csrf = authenticated_project(client)
    demo = client.post(
        f"/api/v1/projects/{project_id}/datasets/import-demo",
        headers={"X-CSRF-Token": csrf},
        json={"demo": "small", "authorization_confirmed": True},
    )
    assert demo.status_code == 201, demo.text
    datasets = client.get(f"/api/v1/projects/{project_id}/datasets").json()
    assert datasets[0]["node_count"] == 35
    assert datasets[0]["relationship_count"] >= 55
    duplicate = client.post(
        f"/api/v1/projects/{project_id}/datasets/import-demo",
        headers={"X-CSRF-Token": csrf},
        json={"demo": "small", "authorization_confirmed": True},
    )
    assert duplicate.status_code == 409
    assert len(client.get(f"/api/v1/projects/{project_id}/datasets").json()) == 1

    raw = small_json_dataset(unknown=True)
    validation = client.post(
        f"/api/v1/projects/{project_id}/datasets/validate-json",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("dataset.json", raw, "application/json")},
    )
    assert validation.status_code == 200
    body = validation.json()
    assert body["valid"] is True
    assert any(item["code"] == "unknown_node_type" for item in body["messages"])
    blocked = client.post(
        f"/api/v1/projects/{project_id}/datasets/import-json",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("dataset.json", raw, "application/json")},
        data={
            "validation_digest": body["digest"],
            "authorization_confirmed": "true",
            "name": "Unknown node test",
        },
    )
    assert blocked.status_code == 422
    imported = client.post(
        f"/api/v1/projects/{project_id}/datasets/import-json",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("dataset.json", raw, "application/json")},
        data={
            "validation_digest": body["digest"],
            "authorization_confirmed": "true",
            "acknowledged_warnings": "unknown_node_type",
            "name": "Unknown node test",
        },
    )
    assert imported.status_code == 201, imported.text


def test_invalid_json_and_unsafe_zip_leave_no_import(client: TestClient) -> None:
    project_id, csrf = authenticated_project(client)
    invalid = client.post(
        f"/api/v1/projects/{project_id}/datasets/validate-json",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("broken.json", b'{"nodes": [}', "application/json")},
    )
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("../nodes.csv", "id,type,name\nu,User,Unsafe")
        archive.writestr("relationships.csv", "id,source,target,type\n")
    unsafe = client.post(
        f"/api/v1/projects/{project_id}/datasets/validate-csv",
        headers={"X-CSRF-Token": csrf},
        files={"zip_file": ("unsafe.zip", archive_bytes.getvalue(), "application/zip")},
    )
    assert unsafe.status_code == 200
    assert unsafe.json()["valid"] is False
    assert unsafe.json()["messages"][0]["code"] == "unsafe_archive_entry"
    assert client.get(f"/api/v1/projects/{project_id}/datasets").json() == []
