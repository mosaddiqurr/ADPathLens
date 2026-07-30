from __future__ import annotations

import argparse
import sys
from typing import Any

import httpx

AUTH_ACK = "I confirm that I own this target or have explicit authorization to test it."
LAB_ACK = (
    "I confirm this private or loopback destination is an authorized local laboratory."
)


class Seeder:
    def __init__(
        self,
        base_url: str,
        setup_token: str,
        email: str,
        password: str,
    ) -> None:
        self.client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/api/v1",
            timeout=10,
            follow_redirects=False,
            trust_env=False,
        )
        self.setup_token = setup_token
        self.email = email
        self.password = password
        self.csrf = ""

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"X-CSRF-Token": self.csrf} if method not in {"GET", "HEAD"} else {}
        response = self.client.request(method, path, json=json, headers=headers)
        if response.is_error:
            try:
                detail = response.json().get("detail", "request failed")
            except ValueError:
                detail = "request failed"
            raise RuntimeError(
                f"{method} {path}: HTTP {response.status_code}: {detail}"
            )
        return None if response.status_code == 204 else response.json()

    def authenticate(self) -> None:
        setup = self.request("GET", "/auth/setup-status")
        preauth = self.request("GET", "/auth/csrf")
        self.csrf = str(preauth["csrf_token"])
        if setup["setup_required"]:
            result = self.request(
                "POST",
                "/auth/setup",
                json={
                    "setup_token": self.setup_token,
                    "email": self.email,
                    "display_name": "AuthZDiff Local Administrator",
                    "password": self.password,
                    "authorization_acknowledgement": AUTH_ACK,
                },
            )
        else:
            result = self.request(
                "POST",
                "/auth/login",
                json={"email": self.email, "password": self.password},
            )
        self.csrf = str(result["csrf_token"])

    @staticmethod
    def named(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
        return next((row for row in rows if row.get("name") == name), None)

    def reset(self, project_id: str) -> None:
        self.request("POST", "/demo/reset", json={"project_id": project_id})

    def seed(self) -> str:
        projects = self.request("GET", "/projects")
        project = self.named(projects, "AuthZDiff Deterministic Demo")
        if project is None:
            project = self.request(
                "POST",
                "/projects",
                json={
                    "name": "AuthZDiff Deterministic Demo",
                    "description": (
                        "Fictional local fixtures for authorized comparison training."
                    ),
                },
            )
        project_id = str(project["id"])

        targets = self.request("GET", f"/projects/{project_id}/targets")
        target = self.named(targets, "Isolated demo target")
        if target is None:
            target = self.request(
                "POST",
                f"/projects/{project_id}/targets",
                json={
                    "name": "Isolated demo target",
                    "base_url": "http://127.0.0.1:8021",
                    "allowed_path_prefixes": [
                        "/secure",
                        "/vulnerable",
                        "/ambiguous",
                        "/slow",
                    ],
                    "allowed_methods": ["GET", "HEAD"],
                    "local_test_target": True,
                    "request_budget": 200,
                    "maximum_response_bytes": 2 * 1024 * 1024,
                    "concurrency_limit": 2,
                    "timeout_seconds": 10,
                    "per_run_timeout_seconds": 60,
                    "follow_redirects": False,
                    "maximum_redirects": 0,
                    "tls_policy": "strict",
                },
            )
            target = self.request(
                "POST",
                f"/targets/{target['id']}/confirm-authorization",
                json={"acknowledgement": AUTH_ACK},
            )
            target = self.request(
                "POST",
                f"/targets/{target['id']}/confirm-lab",
                json={"acknowledgement": LAB_ACK, "allow_private_networks": True},
            )
            self.request(
                "POST",
                f"/targets/{target['id']}/allowlist",
                json={
                    "entry_type": "ip",
                    "value": "127.0.0.1",
                    "allowed_port": 8021,
                    "notes": "Exact loopback fixture address.",
                },
            )
            self.request("POST", f"/targets/{target['id']}/validate", json={})
            target = self.request(
                "PATCH", f"/targets/{target['id']}", json={"is_active": True}
            )
        target_id = str(target["id"])

        profiles = self.request("GET", f"/projects/{project_id}/sessions")
        definitions = [
            ("Demo Administrator", "administrator", False, "demo-admin-token"),
            ("Demo User A", "user-a", False, "demo-user-a-token"),
            ("Demo User B", "user-b", False, "demo-user-b-token"),
            ("Demo Anonymous", "anonymous", True, None),
        ]
        for name, role, anonymous, token in definitions:
            if self.named(profiles, name) is None:
                profile = self.request(
                    "POST",
                    f"/projects/{project_id}/sessions",
                    json={
                        "target_id": target_id,
                        "name": name,
                        "role_label": role,
                        "description": "Synthetic local fixture identity.",
                        "is_anonymous": anonymous,
                        "authorization_header": token,
                        "custom_headers": [],
                    },
                )
                profiles.append(profile)

        collections = self.request("GET", f"/projects/{project_id}/request-collections")
        collection = self.named(collections, "Demo authorization checks")
        if collection is None:
            collection = self.request(
                "POST",
                f"/projects/{project_id}/request-collections",
                json={
                    "target_id": target_id,
                    "name": "Demo authorization checks",
                    "description": "Secure controls and intentionally vulnerable counterparts.",
                },
            )
        collection_id = str(collection["id"])

        requests = self.request("GET", f"/projects/{project_id}/requests")
        request_definitions = [
            ("Secure vertical control", "/secure/admin/users"),
            ("Vulnerable vertical fixture", "/vulnerable/admin/users"),
            ("Secure horizontal control", "/secure/documents/doc-a"),
            ("Vulnerable horizontal fixture", "/vulnerable/documents/doc-a"),
            ("Sensitive-field fixture", "/vulnerable/accounts/user-a"),
            ("Existence-leak fixture", "/vulnerable/existence/documents/doc-a"),
            ("Ambiguous fixture", "/ambiguous"),
        ]
        for name, path in request_definitions:
            if self.named(requests, name) is None:
                saved = self.request(
                    "POST",
                    f"/projects/{project_id}/requests/manual",
                    json={
                        "collection_id": collection_id,
                        "target_id": target_id,
                        "name": name,
                        "method": "GET",
                        "path": path,
                        "query_parameters": [],
                        "headers": [],
                        "body": "",
                        "content_type": None,
                        "approved_state_change": False,
                        "expected_markers": [],
                        "tags": ["synthetic-demo"],
                        "sensitivity": "internal",
                    },
                )
                requests.append(saved)

        cases = self.request("GET", f"/projects/{project_id}/test-cases")
        admin = self.named(profiles, "Demo Administrator")
        user_a = self.named(profiles, "Demo User A")
        user_b = self.named(profiles, "Demo User B")
        comparisons = [
            (
                "Vertical fixture comparison",
                "Vulnerable vertical fixture",
                admin,
                user_a,
                "lower_denied",
            ),
            (
                "Horizontal fixture comparison",
                "Vulnerable horizontal fixture",
                user_a,
                user_b,
                "ownership_separation",
            ),
        ]
        for name, request_name, high, low, expectation in comparisons:
            if self.named(cases, name) is None and high is not None and low is not None:
                request_definition = self.named(requests, request_name)
                if request_definition is None:
                    raise RuntimeError(f"Seed request is missing: {request_name}")
                self.request(
                    "POST",
                    f"/projects/{project_id}/test-cases",
                    json={
                        "target_id": target_id,
                        "imported_request_id": request_definition["id"],
                        "name": name,
                        "description": "Deterministic synthetic fixture comparison.",
                        "high_privilege_session_id": high["id"],
                        "low_privilege_session_id": low["id"],
                        "expected_behaviour": expectation,
                        "custom_expectation": "",
                        "approved_state_change": False,
                        "variables": [],
                        "ignored_json_paths": [],
                        "unordered_json_paths": [],
                        "ignored_headers": [],
                        "ignored_text_patterns": [],
                    },
                )
        return project_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the isolated AuthZDiff demo.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--setup-token", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--reset-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    seeder = Seeder(
        arguments.base_url,
        arguments.setup_token,
        arguments.email,
        arguments.password,
    )
    try:
        seeder.authenticate()
        if arguments.reset_only:
            projects = seeder.request("GET", "/projects")
            project = seeder.named(projects, "AuthZDiff Deterministic Demo")
            if project is None:
                raise RuntimeError(
                    "The deterministic demo project has not been seeded."
                )
            seeder.reset(str(project["id"]))
            print("Synthetic demo fixtures reset.")
        else:
            project_id = seeder.seed()
            print(f"Deterministic demo ready in project {project_id}.")
        return 0
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"Demo operation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        seeder.client.close()


if __name__ == "__main__":
    raise SystemExit(main())
