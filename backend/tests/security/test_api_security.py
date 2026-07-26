from fastapi.testclient import TestClient

from tests.test_graph_analysis import import_small_demo
from tests.test_imports import authenticated_project


def test_request_ids_security_headers_cookie_and_rule_configuration(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "synthetic-request-42"})
    assert response.headers["X-Request-ID"] == "synthetic-request-42"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]

    project_id, csrf = authenticated_project(client)
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "Correct-Horse-Battery-Staple-123",
        },
    )
    set_cookie = login.headers["set-cookie"].lower()
    csrf = login.json()["csrf_token"]
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    configured = client.post(
        "/api/v1/risk/rules/APL-001/configuration",
        headers={"X-CSRF-Token": csrf},
        json={
            "enabled": False,
            "relationship_weights": {"ResetPassword": 2.5},
            "scoring_overrides": {},
        },
    )
    assert configured.status_code == 201, configured.text
    assert configured.json()["version"] == 1
    snapshot_id = import_small_demo(client, project_id, csrf)
    scan = client.post(
        f"/api/v1/snapshots/{snapshot_id}/risk-scan",
        headers={"X-CSRF-Token": csrf},
    )
    assert scan.status_code == 200
    findings = client.get(f"/api/v1/projects/{project_id}/findings", params={"page_size": 100}).json()["items"]
    assert all(finding["rule_id"] != "APL-001" for finding in findings)


def test_report_and_project_idor_return_not_found(client: TestClient) -> None:
    project_id, csrf = authenticated_project(client)
    snapshot_id = import_small_demo(client, project_id, csrf)
    report = client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers={"X-CSRF-Token": csrf},
        json={
            "snapshot_id": snapshot_id,
            "report_type": "findings",
            "format": "json",
        },
    )
    assert report.status_code == 201, report.text

    other = client.post(
        "/api/v1/users",
        headers={"X-CSRF-Token": csrf},
        json={
            "email": "isolated@example.com",
            "display_name": "Isolated Analyst",
            "password": "Isolated-Correct-Horse-Battery-42",
            "role": "analyst",
        },
    )
    assert other.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "isolated@example.com",
            "password": "Isolated-Correct-Horse-Battery-42",
        },
    )
    assert login.status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
    assert client.get(f"/api/v1/reports/{report.json()['id']}").status_code == 404
    assert client.get(f"/api/v1/reports/{report.json()['id']}/download").status_code == 404
