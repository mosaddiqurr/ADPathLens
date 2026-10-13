"""Publication regressions: conservative evidence, redaction, and bounded exports."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.comparison.normalization import redact_json, redact_text
from app.core.config import Settings
from app.main import app

client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)


def capture(
    access: str, status: int, request_overrides: dict[str, Any] | None = None
) -> dict[str, str]:
    return {
        "filename": "capture.har",
        "content": json.dumps(
            {
                "log": {
                    "entries": [
                        {
                            "_authzdiff": {"principal": "Alice", "access": access},
                            "request": {
                                "method": "POST",
                                "url": "https://example.invalid/items/one",
                                **(request_overrides or {}),
                            },
                            "response": {
                                "status": status,
                                "content": {
                                    "mimeType": "text/plain",
                                    "text": "forbidden" if status == 403 else "visible",
                                },
                            },
                        }
                    ]
                }
            }
        ),
    }


@pytest.mark.parametrize(
    "first, second",
    [
        (
            {"url": "https://example.invalid/items/one%2Ftwo"},
            {"url": "https://example.invalid/items/one/two"},
        ),
        (
            {"postData": {"params": [{"name": "item", "value": "one"}]}},
            {"postData": {"params": [{"name": "item", "value": "two"}]}},
        ),
        (
            {"headers": [{"name": "X-Tenant-ID", "value": "one"}]},
            {"headers": [{"name": "X-Tenant-ID", "value": "two"}]},
        ),
        (
            {"postData": {"mimeType": "text/plain", "text": "one"}},
            {"postData": {"mimeType": "application/json", "text": "one"}},
        ),
        (
            {"url": "https://example.invalid/items/one?id=one"},
            {"url": "https://example.invalid/items/one?id=two"},
        ),
    ],
)
def test_changed_request_context_never_proves_access_transition(
    first: dict[str, Any], second: dict[str, Any]
) -> None:
    response = client.post(
        "/api/v1/compare",
        json={"before": capture("denied", 403, first), "after": capture("allowed", 200, second)},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["summary"]["gained"] == result["summary"]["lost"] == 0
    assert result["summary"]["review"] == 2
    assert all(c["category"] == "Capture coverage changed" for c in result["changes"])


def test_credential_rotation_does_not_change_annotated_identity_or_export_secrets() -> None:
    payload = {
        "before": capture(
            "denied",
            403,
            {
                "url": "https://example.invalid/items/one?apiKey=private-one",
                "headers": [{"name": "Authorization", "value": "Bearer private-one"}],
            },
        ),
        "after": capture(
            "allowed",
            200,
            {
                "url": "https://example.invalid/items/one?apiKey=private-two",
                "headers": [{"name": "Authorization", "value": "Bearer private-two"}],
            },
        ),
    }
    result = client.post("/api/v1/reports/json", json=payload)
    assert result.status_code == 200
    assert result.json()["summary"]["gained"] == 1
    assert "private-one" not in result.text and "private-two" not in result.text
    difference = result.json()["changes"][0]["evidence"]["response_difference"]
    assert difference["status"] == {"before": 403, "after": 200}
    assert difference["text_diff"].startswith("--- Before\n+++ After")


@pytest.mark.parametrize(
    "key", ["apiKey", "accessToken", "X-API-Key", "sessionToken", "Set-Cookie"]
)
def test_sensitive_key_variants_are_redacted(key: str) -> None:
    assert redact_json({key: "tiny-secret"}) == {key: "[REDACTED]"}


@pytest.mark.parametrize(
    "text",
    [
        '"clientSecret": "tiny-secret"',
        "refresh_token=tiny-secret",
        "Cookie: sid=tiny-secret; other=second-secret",
        "authorization: tiny-secret",
        "password='tiny-secret with spaces'",
    ],
)
def test_short_credentials_in_text_are_redacted(text: str) -> None:
    assert "tiny-secret" not in redact_text(text)
    assert "second-secret" not in redact_text(text)


def test_sensitive_response_and_filename_never_enter_reports() -> None:
    payload = {"before": capture("denied", 403), "after": capture("allowed", 200)}
    after = json.loads(payload["after"]["content"])
    after["log"]["entries"][0]["response"].update(
        {
            "headers": [{"name": "Set-Cookie", "value": "sid=tiny-secret"}],
            "content": {
                "mimeType": "application/json",
                "text": json.dumps({"apiKey": "tiny-secret", "visible": "yes"}),
            },
        }
    )
    payload["after"] = {"filename": "token=tiny-secret.har", "content": json.dumps(after)}
    comparison = client.post("/api/v1/compare", json=payload)
    assert comparison.status_code == 200 and "tiny-secret" not in comparison.text
    for output in ("json", "csv", "pdf"):
        response = client.post(f"/api/v1/reports/{output}", json=payload)
        assert response.status_code == 200
        assert b"tiny-secret" not in response.content


def test_large_bounded_snapshot_exports_all_changes() -> None:
    records = [
        {"principal": f"Person {i}", "resource": "Billing", "action": "Read", "effect": "deny"}
        for i in range(2000)
    ]
    payload = {
        "before": {"filename": "before.json", "content": json.dumps(records)},
        "after": {
            "filename": "after.json",
            "content": json.dumps([{**record, "effect": "allow"} for record in records]),
        },
    }
    response = client.post("/api/v1/reports/json", json=payload)
    assert response.status_code == 200 and len(response.json()["changes"]) == 2000
    csv_response = client.post("/api/v1/reports/csv", json=payload)
    assert csv_response.status_code == 200
    assert len(list(csv.reader(io.StringIO(csv_response.content.decode("utf-8-sig"))))) == 2001
    pdf = client.post("/api/v1/reports/pdf", json=payload)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://example.invalid/",
        "https://user:secret@example.invalid",
        "https://example.invalid/path",
        "https://example.invalid:99999",
        "null",
    ],
)
def test_invalid_deployment_origins_fail_at_startup(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, allowed_frontend_origins=origin)


def test_exact_cors_and_host_boundaries() -> None:
    for origin, allowed in [("http://localhost:4174", True), ("https://evil.invalid", False)]:
        response = client.options(
            "/api/v1/compare",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == (200 if allowed else 400)
        assert response.headers.get("access-control-allow-origin") == (origin if allowed else None)
    assert client.get("/api/v1/health", headers={"Host": "evil.invalid"}).status_code == 400


@pytest.mark.parametrize(
    "content",
    [
        "",
        "principal,resource,action,effect\n",
        "principal,resource,action,effect\nAlice,Billing,Read,allow\nAlice,Billing,Read,deny",
        'principal,resource,action,effect\n"Alice,Billing,Read,allow',
        "principal,resource,action,effect\nAlice,Billing,Read,allow,extra",
        "principal,resource,action,effect,sensitive\nAlice,Billing,Read,allow,maybe",
        "principal,principal,resource,action,effect\nAlice,Bob,Billing,Read,allow",
    ],
)
def test_invalid_and_empty_csv_is_rejected(content: str) -> None:
    response = client.post("/api/v1/inspect", json={"filename": "input.csv", "content": content})
    assert response.status_code == 422 and set(response.json()) == {"detail"}


def test_har_entry_limit_and_empty_capture() -> None:
    entry = json.loads(capture("allowed", 200)["content"])["log"]["entries"][0]
    entries = []
    for index in range(500):
        entries.append(
            {
                **entry,
                "request": {**entry["request"], "url": f"https://example.invalid/items/{index}"},
            }
        )
    data = {"filename": "large.har", "content": json.dumps({"log": {"entries": entries}})}
    result = client.post("/api/v1/compare", json={"before": data, "after": data})
    assert result.status_code == 200 and result.json()["summary"]["unchanged"] == 500
    for invalid in ([], entries + [entry]):
        response = client.post(
            "/api/v1/inspect",
            json={"filename": "input.har", "content": json.dumps({"log": {"entries": invalid}})},
        )
        assert response.status_code == 422


def test_response_content_type_is_redacted_in_all_evidence() -> None:
    before, after = capture("denied", 403), capture("allowed", 200)
    document = json.loads(after["content"])
    document["log"]["entries"][0]["response"]["content"]["mimeType"] = (
        "text/plain; token=tiny-secret"
    )
    after["content"] = json.dumps(document)
    response = client.post("/api/v1/reports/json", json={"before": before, "after": after})
    assert response.status_code == 200 and "tiny-secret" not in response.text
