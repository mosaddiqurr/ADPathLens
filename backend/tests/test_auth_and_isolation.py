from fastapi.testclient import TestClient


def setup_admin(client: TestClient) -> tuple[dict[str, object], str]:
    response = client.post(
        "/api/v1/auth/setup",
        json={
            "email": "admin@northbridge.example",
            "display_name": "Northbridge Administrator",
            "password": "Correct-Horse-Battery-Staple-42",
            "authorization_confirmed": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), response.json()["csrf_token"]


def test_authentication_csrf_roles_and_project_isolation(client: TestClient) -> None:
    assert client.get("/api/v1/auth/setup-status").json() == {"setup_required": True}
    auth, csrf = setup_admin(client)
    assert auth["user"]["role"] == "administrator"
    assert client.get("/api/v1/auth/me").status_code == 200

    workspaces = client.get("/api/v1/workspaces").json()
    assert len(workspaces) == 1
    workspace_id = workspaces[0]["id"]

    missing_csrf = client.post(
        "/api/v1/projects",
        json={"workspace_id": workspace_id, "name": "No CSRF project"},
    )
    assert missing_csrf.status_code == 403

    project = client.post(
        "/api/v1/projects",
        headers={"X-CSRF-Token": csrf},
        json={
            "workspace_id": workspace_id,
            "name": "Northbridge Lab",
            "description": "Synthetic data only",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    other_user = client.post(
        "/api/v1/users",
        headers={"X-CSRF-Token": csrf},
        json={
            "email": "other@northbridge.example",
            "display_name": "Other Analyst",
            "password": "Another-Correct-Horse-Battery-42",
            "role": "analyst",
        },
    )
    assert other_user.status_code == 201, other_user.text
    admin_cookie = client.cookies.get("adpathlens_session")
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "other@northbridge.example",
            "password": "Another-Correct-Horse-Battery-42",
        },
    )
    assert login.status_code == 200
    assert client.get("/api/v1/projects").json() == []
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
    client.cookies.set("adpathlens_session", admin_cookie)

    viewer = client.post(
        "/api/v1/users",
        headers={"X-CSRF-Token": csrf},
        json={
            "email": "viewer@northbridge.example",
            "display_name": "Read Only",
            "password": "Viewer-Correct-Horse-Battery-42",
            "role": "viewer",
        },
    )
    viewer_id = viewer.json()["id"]
    membership = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers={"X-CSRF-Token": csrf},
        json={"user_id": viewer_id, "role": "viewer"},
    )
    assert membership.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "viewer@northbridge.example",
            "password": "Viewer-Correct-Horse-Battery-42",
        },
    )
    viewer_csrf = login.json()["csrf_token"]
    assert len(client.get("/api/v1/projects").json()) == 1
    blocked = client.post(
        "/api/v1/projects",
        headers={"X-CSRF-Token": viewer_csrf},
        json={"workspace_id": workspace_id, "name": "Forbidden"},
    )
    assert blocked.status_code == 403


def test_invalid_login_is_generic(client: TestClient) -> None:
    setup_admin(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email or password is incorrect."
