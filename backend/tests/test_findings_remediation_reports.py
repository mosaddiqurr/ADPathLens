import csv
import io

from fastapi.testclient import TestClient

from tests.test_graph_analysis import import_small_demo
from tests.test_imports import authenticated_project


def _relationship(client: TestClient, snapshot_id: str, external_id: str) -> dict[str, object]:
    response = client.get(
        f"/api/v1/snapshots/{snapshot_id}/relationships",
        params={"page_size": 100},
    )
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["external_id"] == external_id)


def test_findings_notes_remediation_comparison_and_reports(
    client: TestClient,
) -> None:
    project_id, csrf = authenticated_project(client)
    source_snapshot_id = import_small_demo(client, project_id, csrf)

    scan = client.post(
        f"/api/v1/snapshots/{source_snapshot_id}/risk-scan",
        headers={"X-CSRF-Token": csrf},
    )
    assert scan.status_code == 200, scan.text
    assert scan.json()["total"] > 0
    findings = client.get(
        f"/api/v1/projects/{project_id}/findings",
        params={"page_size": 100},
    ).json()["items"]
    finding = findings[0]

    evidence = client.get(f"/api/v1/findings/{finding['id']}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["limitations"]
    note = client.post(
        f"/api/v1/findings/{finding['id']}/notes",
        headers={"X-CSRF-Token": csrf},
        json={"body": "Validated against the fictional lab source."},
    )
    assert note.status_code == 201, note.text
    reviewed = client.patch(
        f"/api/v1/findings/{finding['id']}",
        headers={"X-CSRF-Token": csrf},
        json={
            "status": "confirmed",
            "status_note": "Evidence reviewed in the synthetic lab.",
            "reviewer_notes": "Human review completed.",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "confirmed"
    history = client.get(f"/api/v1/findings/{finding['id']}/history")
    assert [item["new_status"] for item in history.json()] == ["draft", "confirmed"]

    relationship = _relationship(client, source_snapshot_id, "rel-helpdesk-priya")
    plan = client.post(
        f"/api/v1/projects/{project_id}/remediation-plans",
        headers={"X-CSRF-Token": csrf},
        json={
            "source_snapshot_id": source_snapshot_id,
            "name": "Remove excess password reset",
            "description": "Fictional simulation only.",
        },
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]
    action = client.post(
        f"/api/v1/remediation-plans/{plan_id}/actions",
        headers={"X-CSRF-Token": csrf},
        json={
            "finding_id": finding["id"],
            "action_type": "remove_password_reset",
            "target_relationship_id": relationship["id"],
            "description": "Remove the unnecessary reset permission.",
        },
    )
    assert action.status_code == 201, action.text
    preview = client.post(
        f"/api/v1/remediation-plans/{plan_id}/preview",
        headers={"X-CSRF-Token": csrf},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["preview_relationship_count"] == (preview.json()["source_relationship_count"] - 1)
    assert preview.json()["simulation_only"] is True

    derived = client.post(
        f"/api/v1/remediation-plans/{plan_id}/create-snapshot",
        headers={"X-CSRF-Token": csrf},
    )
    assert derived.status_code == 201, derived.text
    derived_snapshot_id = derived.json()["id"]
    assert derived.json()["parent_snapshot_id"] == source_snapshot_id
    assert _relationship(client, source_snapshot_id, "rel-helpdesk-priya")["active"] is True
    derived_relationships = client.get(
        f"/api/v1/snapshots/{derived_snapshot_id}/relationships",
        params={"page_size": 100},
    ).json()["items"]
    assert all(item["external_id"] != "rel-helpdesk-priya" for item in derived_relationships)

    comparison = client.post(
        f"/api/v1/projects/{project_id}/comparisons",
        headers={"X-CSRF-Token": csrf},
        json={
            "before_snapshot_id": source_snapshot_id,
            "after_snapshot_id": derived_snapshot_id,
        },
    )
    assert comparison.status_code == 201, comparison.text
    assert comparison.json()["relationships_removed"] == 1
    relationship_diff = client.get(f"/api/v1/comparisons/{comparison.json()['id']}/relationships")
    assert relationship_diff.status_code == 200
    assert any(
        item["external_id"] == "rel-helpdesk-priya" and item["change"] == "removed"
        for item in relationship_diff.json()["items"]
    )

    injected = client.post(
        f"/api/v1/projects/{project_id}/findings",
        headers={"X-CSRF-Token": csrf},
        json={
            "snapshot_id": derived_snapshot_id,
            "title": "=2+2 synthetic title",
            "category": "test",
            "severity": "low",
            "confidence": "high",
            "description": "<script>alert('fictional')</script>",
            "impact": "Synthetic impact.",
            "remediation": "Synthetic remediation.",
            "limitations": "Synthetic test only.",
        },
    )
    assert injected.status_code == 201, injected.text

    for report_format in ("json", "csv", "html", "pdf"):
        report = client.post(
            f"/api/v1/projects/{project_id}/reports",
            headers={"X-CSRF-Token": csrf},
            json={
                "snapshot_id": derived_snapshot_id,
                "report_type": "findings",
                "format": report_format,
            },
        )
        assert report.status_code == 201, report.text
        assert len(report.json()["file_hash"]) == 64
        download = client.get(f"/api/v1/reports/{report.json()['id']}/download")
        assert download.status_code == 200, download.text
        if report_format == "json":
            assert download.json()["schema_version"] == "1.0"
            assert len(download.json()["report_hash"]) == 64
        elif report_format == "csv":
            rows = list(csv.DictReader(io.StringIO(download.content.decode("utf-8-sig"))))
            assert any(row["title"].startswith("'=") for row in rows)
        elif report_format == "html":
            html = download.text
            assert "&lt;script&gt;" in html
            assert "<script>alert" not in html
        else:
            assert download.content.startswith(b"%PDF")
