from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)


def input_file(name: str) -> dict[str, str]:
    return {"filename": name, "content": (ROOT / "examples" / name).read_text(encoding="utf-8")}


def snapshot(records: list[dict[str, Any]]) -> dict[str, str]:
    return {"filename": "state.json", "content": json.dumps(records)}


def record(**overrides: Any) -> dict[str, Any]:
    return {
        "principal": "Alice",
        "resource": "Billing",
        "action": "Read",
        "effect": "allow",
        **overrides,
    }


def compare(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    response = client.post("/api/v1/compare", json={"before": before, "after": after})
    assert response.status_code == 200, response.text
    return response.json()


def test_no_accounts_or_old_product_routes() -> None:
    assert client.get("/api/v1/ready").json()["processing"] == "memory-only"
    for route in ("/auth/me", "/projects", "/users", "/runs", "/audit"):
        assert client.get("/api/v1" + route).status_code == 404


def test_final_workflow_and_export_evidence() -> None:
    before, after = input_file("snapshot-before.json"), input_file("snapshot-after.json")
    inspected = client.post("/api/v1/inspect", json=before)
    assert inspected.status_code == 200
    assert inspected.json()["record_count"] == 5
    result = compare(before, after)
    assert result["summary"] == {
        "total": 5,
        "gained": 3,
        "lost": 1,
        "risky": 3,
        "review": 1,
        "unchanged": 1,
    }
    changes = {change["principal"]: change for change in result["changes"]}
    assert changes["Alice"]["severity"] == "high"
    assert changes["Alice"]["before"] == "Viewer"
    assert changes["Alice"]["after"] == "Administrator"
    assert changes["Public"]["severity"] == "critical"
    assert changes["Bob"]["change"] == "lost"
    assert changes["Dana"]["severity"] == "info"
    assert changes["Developer"]["change"] == "changed"
    payload = {"before": before, "after": after}
    exported = client.post("/api/v1/reports/json", json=payload)
    assert exported.json()["changes"] == result["changes"]
    assert exported.json()["summary"] == result["summary"]
    assert exported.headers["cache-control"] == "no-store"
    pdf = client.post("/api/v1/reports/pdf", json=payload)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-disposition"] == 'attachment; filename="authzdiff-report.pdf"'
    csv = client.post("/api/v1/reports/csv", json=payload)
    assert csv.status_code == 200 and b"Alice" in csv.content


def test_no_change_and_json_csv_compatibility() -> None:
    before = input_file("snapshot-before.json")
    result = compare(before, before)
    assert result["summary"]["total"] == 0
    assert result["summary"]["unchanged"] == 5
    assert compare(before, input_file("snapshot-before.csv"))["changes"] == []


@pytest.mark.parametrize(
    "content",
    [
        "{",
        "null",
        '[{"principal":null}]',
        '[{"principal":"Alice","principal":"Bob"}]',
        '{"records": [NaN]}',
        "[" * 40 + "0" + "]" * 40,
    ],
)
def test_malformed_input_is_safe(content: str) -> None:
    response = client.post(
        "/api/v1/inspect",
        content=json.dumps({"filename": "bad.json", "content": content}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in {415, 422}
    assert set(response.json()) == {"detail"}
    assert "Traceback" not in response.text


def test_unsupported_incompatible_and_empty_inputs() -> None:
    assert (
        client.post("/api/v1/inspect", json={"filename": "bad.exe", "content": "data"}).status_code
        == 415
    )
    policy = snapshot([])
    policy["content"] = '{"Version":"2012-10-17","Statement":[]}'
    assert client.post("/api/v1/inspect", json=policy).status_code == 415
    assert (
        client.post("/api/v1/inspect", json=snapshot([])).json()["detail"]
        == "No comparable authorization records were found."
    )
    response = client.post(
        "/api/v1/compare",
        json={
            "before": input_file("snapshot-before.json"),
            "after": input_file("capture-after.har"),
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "The two inputs use incompatible formats."


def test_duplicate_rows_and_limits_reject_without_silent_truncation() -> None:
    for rows in ([record(), record()], [record(principal=str(i)) for i in range(2001)]):
        response = client.post("/api/v1/inspect", json=snapshot(rows))
        assert response.status_code == 422
    oversized = {"filename": "big.json", "content": "é" * (3 * 1024 * 1024)}
    assert client.post("/api/v1/inspect", json=oversized).status_code == 413


def test_removed_deny_does_not_claim_access_gain() -> None:
    result = compare(snapshot([record(effect="deny")]), snapshot([record(principal="Bob")]))
    change = next(c for c in result["changes"] if c["principal"] == "Alice")
    assert change["change"] == "changed" and change["severity"] == "medium"
    assert "does not establish" in change["why"]


def test_arbitrary_roles_do_not_imply_escalation() -> None:
    result = compare(snapshot([record(role="Blue")]), snapshot([record(role="Green")]))
    assert result["changes"][0]["change"] == "changed"
    assert result["summary"]["risky"] == 0


def test_denied_custom_role_does_not_invent_a_recognized_role_hierarchy() -> None:
    result = compare(
        snapshot([record(effect="deny", role="Blue")]),
        snapshot([record(role="Green")]),
    )
    change = result["changes"][0]
    assert change["change"] == "gained" and change["severity"] == "high"
    assert change["category"] == "Explicit deny removed"
    assert "recognized role" not in change["why"]


def test_management_action_risk_requires_a_new_exact_action_grant() -> None:
    result = compare(
        snapshot([record(principal="Unchanged")]),
        snapshot(
            [
                record(principal="Unchanged"),
                record(principal="Bob", action="Billing.Manage"),
                record(principal="Carol", action="not-admin"),
            ]
        ),
    )
    changes = {change["principal"]: change for change in result["changes"]}
    assert changes["Bob"]["severity"] == "high"
    assert changes["Carol"]["severity"] == "info"
    role_change = compare(
        snapshot([record(action="Manage", role="Viewer")]),
        snapshot([record(action="Manage", role="Developer")]),
    )["changes"][0]
    assert role_change["severity"] == "medium"
    assert "Administrator" not in role_change["why"]


def test_new_admin_label_is_risky_without_inventing_unknown_hierarchy() -> None:
    result = compare(snapshot([record(role="Custom")]), snapshot([record(role="Admin")]))
    assert result["changes"][0]["change"] == "changed"
    assert result["changes"][0]["severity"] == "high"
    assert "permissions are unknown" in result["changes"][0]["why"]


@pytest.mark.parametrize(
    "candidate, severity",
    [
        ({"action": "*"}, "high"),
        ({"sensitive": True}, "medium"),
        ({"principal": "anonymous"}, "high"),
    ],
)
def test_specific_gain_risks(candidate: dict[str, Any], severity: str) -> None:
    result = compare(
        snapshot([record(principal="Unchanged")]),
        snapshot([record(principal="Unchanged"), record(**candidate)]),
    )
    assert result["summary"]["gained"] == 1
    assert result["changes"][0]["severity"] == severity


def test_missing_capture_evidence_does_not_claim_gain() -> None:
    before, after = input_file("capture-before.har"), input_file("capture-after.har")
    document = json.loads(after["content"])
    document["log"]["entries"][0]["response"]["content"] = {
        "size": 100,
        "mimeType": "application/json",
    }
    after["content"] = json.dumps(document)
    result = compare(before, after)
    assert result["summary"]["gained"] == 0
    assert result["summary"]["review"] == 1
    assert result["notes"]


@pytest.mark.parametrize(
    "content", ["\ud800", json.dumps([record(principal="\ud800")]), "[1e9999]"]
)
def test_invalid_unicode_and_nonfinite_numbers_are_rejected(content: str) -> None:
    response = client.post(
        "/api/v1/inspect",
        content=json.dumps({"filename": "bad.json", "content": content}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_har_transitions_require_correlated_context() -> None:
    result = compare(input_file("capture-before.har"), input_file("capture-after.har"))
    assert result["summary"]["gained"] == 1
    assert result["summary"]["lost"] == 1
    changes = {c["principal"]: c for c in result["changes"]}
    assert changes["Alice"]["evidence"]["before"]["status"] == 403
    assert changes["Alice"]["evidence"]["after"]["status"] == 200
    assert changes["Bob"]["before"] == "Allowed · HTTP 200"
    assert changes["Bob"]["after"] == "Denied · HTTP 403"
    raw = []
    for name in ("capture-before.har", "capture-after.har"):
        data = input_file(name)
        document = json.loads(data["content"])
        for entry in document["log"]["entries"]:
            entry.pop("_authzdiff")
        data["content"] = json.dumps(document)
        raw.append(data)
    unannotated = compare(*raw)
    assert unannotated["summary"]["gained"] == unannotated["summary"]["lost"] == 0
    assert unannotated["summary"]["review"] == 2
    assert unannotated["summary"]["risky"] == 0
    assert unannotated["notes"]


def test_malformed_repeated_and_traversal_har_are_rejected() -> None:
    data = input_file("capture-before.har")
    document = json.loads(data["content"])
    for broken in (
        {"log": {}},
        {"log": {"entries": [None]}},
        {"log": {"entries": document["log"]["entries"] * 2}},
    ):
        response = client.post(
            "/api/v1/inspect", json={"filename": "broken.har", "content": json.dumps(broken)}
        )
        assert response.status_code == 422
    document["log"]["entries"][0]["request"]["url"] = "https://example.invalid/%252e%252e/private"
    assert (
        client.post(
            "/api/v1/inspect", json={"filename": "broken.har", "content": json.dumps(document)}
        ).status_code
        == 422
    )


def test_origin_no_cookies_and_display_only_filenames() -> None:
    data = input_file("snapshot-before.json")
    data["filename"] = "../../private/baseline.json"
    response = client.post("/api/v1/inspect", json=data)
    assert response.json()["filename"] == "baseline.json"
    assert "set-cookie" not in response.headers
    assert (
        client.post(
            "/api/v1/inspect", json=data, headers={"Origin": "https://evil.invalid"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/inspect", content="not-json").status_code == 415
