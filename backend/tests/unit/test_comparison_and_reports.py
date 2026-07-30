from __future__ import annotations

import csv
import io

import pytest

from app.comparison.engine import ENGINE_VERSION, compare_observations
from app.models import Observation
from app.reporting.generator import render_csv, render_html


def _observation(
    *,
    status: int | None,
    excerpt: str,
    structural: dict[str, object] | None = None,
    denied: bool = False,
    error: str | None = None,
    truncated: bool = False,
) -> Observation:
    return Observation(
        status_code=status,
        response_length=len(excerpt),
        sanitized_excerpt=excerpt,
        sanitized_body_hash="same" if excerpt == "same" else excerpt,
        structural_representation=structural,
        access_denied_marker=denied,
        error_category=error,
        body_truncated=truncated,
    )


def test_rules_engine_is_versioned_and_recognizes_expected_denial() -> None:
    decision = compare_observations(
        _observation(status=200, excerpt="administrator data"),
        _observation(status=403, excerpt="forbidden", denied=True),
        expected_behaviour="lower_denied",
        is_state_changing=False,
    )
    assert ENGINE_VERSION == "authzdiff-rules/1.0"
    assert decision.classification == "expected_access_control"
    assert decision.candidate is False


def test_similar_success_is_only_a_review_candidate() -> None:
    high = _observation(
        status=200,
        excerpt="same",
        structural={"email": "demo@example.invalid", "role": "administrator"},
    )
    low = _observation(
        status=200,
        excerpt="same",
        structural={"email": "demo@example.invalid", "role": "administrator"},
    )
    decision = compare_observations(
        high,
        low,
        expected_behaviour="lower_denied",
        is_state_changing=False,
    )
    assert decision.classification == "potential_vertical_authorization_issue"
    assert decision.candidate is True
    assert "not proof" in decision.explanation.lower()


@pytest.mark.parametrize(
    ("expectation", "classification"),
    [
        ("ownership_separation", "potential_horizontal_authorization_issue"),
        ("tenant_separation", "potential_missing_project_or_tenant_scoping"),
        ("limited_fields", "potential_excessive_privilege"),
        ("sensitive_fields_limited", "potential_sensitive_field_exposure"),
        ("method_protection", "potential_inconsistent_method_protection"),
        ("baseline_consistency", "potential_authorization_drift"),
    ],
)
def test_expected_behavior_selects_an_explainable_candidate_category(
    expectation: str,
    classification: str,
) -> None:
    decision = compare_observations(
        _observation(status=200, excerpt="same", structural={"owner_id": "user-a"}),
        _observation(status=200, excerpt="same", structural={"owner_id": "user-a"}),
        expected_behaviour=expectation,
        is_state_changing=False,
    )
    assert decision.classification == classification
    assert decision.candidate is True


def test_anonymous_success_is_classified_as_missing_authentication() -> None:
    decision = compare_observations(
        _observation(status=200, excerpt="same"),
        _observation(status=200, excerpt="same"),
        expected_behaviour="authenticated_only",
        is_state_changing=False,
        high_is_anonymous=False,
        low_is_anonymous=True,
    )
    assert decision.classification == "potential_missing_authentication"
    assert decision.candidate is True


def test_explicit_forbidden_response_can_signal_object_existence_leakage() -> None:
    decision = compare_observations(
        _observation(status=200, excerpt='{"id":"doc-b"}'),
        _observation(status=403, excerpt="object exists but belongs to another user", denied=True),
        expected_behaviour="object_existence_indistinguishable",
        is_state_changing=False,
    )
    assert decision.classification == "potential_object_existence_leakage"
    assert decision.severity == "low"
    assert decision.candidate is True
    assert "requires manual validation" in decision.explanation.lower()


def test_not_found_response_is_expected_for_object_existence_concealment() -> None:
    decision = compare_observations(
        _observation(status=200, excerpt='{"id":"doc-b"}'),
        _observation(status=404, excerpt="document not found"),
        expected_behaviour="object_existence_indistinguishable",
        is_state_changing=False,
    )
    assert decision.classification == "expected_object_existence_control"
    assert decision.candidate is False


def test_truncation_forces_an_inconclusive_result() -> None:
    decision = compare_observations(
        _observation(status=200, excerpt="same", truncated=True),
        _observation(status=200, excerpt="same"),
        expected_behaviour="lower_denied",
        is_state_changing=False,
    )
    assert decision.classification == "inconclusive_truncated_evidence"
    assert decision.candidate is False


def _report_payload(title: str) -> dict[str, object]:
    return {
        "project": {"name": "Demo"},
        "generated_at": "2026-07-26T00:00:00Z",
        "content_hash": "abc123",
        "redaction_summary": "Credentials excluded.",
        "limitations": "Manual validation is required.",
        "findings": [
            {
                "title": title,
                "category": "authorization",
                "severity": "medium",
                "confidence": "medium",
                "status": "candidate",
                "target": "https://example.invalid",
                "endpoint": "/admin",
                "description": "<script>alert(1)</script>",
                "remediation": '=HYPERLINK("https://evil.invalid")',
            }
        ],
    }


def test_csv_export_prevents_formula_execution() -> None:
    rows = list(csv.reader(io.StringIO(render_csv(_report_payload("=1+1")).decode("utf-8-sig"))))
    assert rows[1][0] == "'=1+1"
    assert rows[1][-1].startswith("'=")


def test_html_report_escapes_untrusted_finding_content() -> None:
    rendered = render_html(_report_payload("<img src=x onerror=alert(1)>")).decode()
    assert "<img src=x" not in rendered
    assert "&lt;img src=x" in rendered
    assert "<script>alert(1)</script>" not in rendered
