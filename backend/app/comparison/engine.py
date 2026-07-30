from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher, unified_diff
from typing import Any

from app.models import Observation

ENGINE_VERSION = "authzdiff-rules/1.0"
SENSITIVE_KEYS = {
    "email",
    "phone",
    "address",
    "salary",
    "balance",
    "account_number",
    "permissions",
    "role",
    "is_admin",
    "internal_notes",
    "owner_id",
    "user_id",
}


@dataclass(frozen=True)
class ComparisonDecision:
    classification: str
    confidence: str
    severity: str
    explanation: str
    differences: dict[str, Any]
    signals: dict[str, Any]
    candidate: bool
    alternative_explanations: tuple[str, ...] = (
        "The profiles may represent expired or different authentication states.",
        "The endpoint may intentionally return a shared or generic response.",
        "Dynamic target data may have changed between the sequential requests.",
    )
    limitations: tuple[str, ...] = (
        "Response comparison does not prove exploitability or business impact.",
        "Only the configured request, profiles, and bounded response evidence were evaluated.",
    )
    remediation: str = (
        "Validate authentication, role, object ownership, and tenant scope server-side "
        "for every protected operation and HTTP method."
    )


def _flatten(value: Any, path: str = "$") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            result.update(_flatten(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value[:100]):
            result.update(_flatten(item, f"{path}[{index}]"))
    else:
        result[path] = value
    return result


def compare_observations(
    high: Observation,
    low: Observation,
    *,
    expected_behaviour: str,
    is_state_changing: bool,
    high_is_anonymous: bool = False,
    low_is_anonymous: bool = False,
) -> ComparisonDecision:
    high_text = high.sanitized_excerpt or ""
    low_text = low.sanitized_excerpt or ""
    similarity = SequenceMatcher(None, high_text, low_text).ratio()
    high_success = high.status_code is not None and 200 <= high.status_code < 300
    low_success = low.status_code is not None and 200 <= low.status_code < 300
    high_fields = _flatten(high.structural_representation)
    low_fields = _flatten(low.structural_representation)
    shared_paths = sorted(set(high_fields) & set(low_fields))
    sensitive_overlap = sorted(
        path for path in shared_paths if path.rsplit(".", 1)[-1].lower() in SENSITIVE_KEYS
    )
    differences = {
        "status": {"high": high.status_code, "low": low.status_code},
        "content_type": {"high": high.content_type, "low": low.content_type},
        "response_length": {
            "high": high.response_length,
            "low": low.response_length,
            "delta": low.response_length - high.response_length,
        },
        "body_similarity": round(similarity, 4),
        "structure_only_high": sorted(set(high_fields) - set(low_fields))[:200],
        "structure_only_low": sorted(set(low_fields) - set(high_fields))[:200],
        "sensitive_field_overlap": sensitive_overlap,
        "text_diff": "\n".join(
            list(
                unified_diff(
                    high_text.splitlines(),
                    low_text.splitlines(),
                    fromfile="higher-role",
                    tofile="lower-role",
                    lineterm="",
                )
            )[:500]
        ),
    }
    signals = {
        "high_success": high_success,
        "low_success": low_success,
        "low_denied": low.access_denied_marker,
        "high_denied": high.access_denied_marker,
        "similarity_band": (
            "high" if similarity >= 0.9 else "moderate" if similarity >= 0.6 else "low"
        ),
        "truncated_evidence": high.body_truncated or low.body_truncated,
        "network_error": bool(high.error_category or low.error_category),
        "sensitive_overlap_count": len(sensitive_overlap),
    }
    if high.error_category or low.error_category:
        return ComparisonDecision(
            "request_or_comparison_failed",
            "low",
            "informational",
            "At least one observation failed, so authorization behavior could not be compared.",
            differences,
            signals,
            False,
        )
    if high.body_truncated or low.body_truncated:
        return ComparisonDecision(
            "inconclusive_truncated_evidence",
            "low",
            "informational",
            "At least one response was truncated, so the authorization comparison is "
            "inconclusive and requires manual review.",
            differences,
            signals,
            False,
        )
    if (
        expected_behaviour == "object_existence_indistinguishable"
        and high_success
        and low.status_code == 403
    ):
        return ComparisonDecision(
            "potential_object_existence_leakage",
            "medium",
            "low",
            "The authorized profile received the object while the other profile received "
            "an explicit forbidden response. When missing objects use a not-found response, "
            "this difference can reveal object existence and requires manual validation.",
            differences,
            signals,
            True,
        )
    if (
        expected_behaviour == "object_existence_indistinguishable"
        and high_success
        and low.status_code == 404
    ):
        return ComparisonDecision(
            "expected_object_existence_control",
            "high",
            "informational",
            "The authorized profile received the object while the other profile received "
            "the configured not-found response.",
            differences,
            signals,
            False,
        )
    if high_success and low.access_denied_marker and not low_success:
        return ComparisonDecision(
            "expected_access_control",
            "high",
            "informational",
            "The higher-privileged profile succeeded while the lower profile was denied.",
            differences,
            signals,
            False,
        )
    concern_expected = expected_behaviour in {
        "lower_denied",
        "limited_fields",
        "ownership_separation",
        "different_records",
        "authenticated_only",
        "tenant_separation",
        "sensitive_fields_limited",
        "method_protection",
        "object_existence_indistinguishable",
        "baseline_consistency",
    }
    strong_similarity = similarity >= 0.9 or high.sanitized_body_hash == low.sanitized_body_hash
    if (
        concern_expected
        and high_success
        and low_success
        and (strong_similarity or sensitive_overlap or is_state_changing)
    ):
        if low_is_anonymous and not high_is_anonymous:
            classification = "potential_missing_authentication"
        else:
            classification = {
                "ownership_separation": "potential_horizontal_authorization_issue",
                "different_records": "potential_horizontal_authorization_issue",
                "tenant_separation": "potential_missing_project_or_tenant_scoping",
                "limited_fields": "potential_excessive_privilege",
                "sensitive_fields_limited": "potential_sensitive_field_exposure",
                "method_protection": "potential_inconsistent_method_protection",
                "object_existence_indistinguishable": ("potential_object_existence_leakage"),
                "baseline_consistency": "potential_authorization_drift",
                "authenticated_only": "potential_missing_authentication",
            }.get(expected_behaviour, "potential_vertical_authorization_issue")
        severity = "high" if is_state_changing else "medium"
        confidence = "high" if strong_similarity and not signals["truncated_evidence"] else "medium"
        return ComparisonDecision(
            classification,
            confidence,
            severity,
            "Both profiles received successful responses with authorization-relevant overlap. "
            "This is a candidate requiring human review, not proof of exploitability.",
            differences,
            signals,
            True,
        )
    if high_success and low_success:
        return ComparisonDecision(
            (
                "different_content_same_access_status"
                if similarity < 0.9
                else "similar_successful_responses"
            ),
            "low",
            "informational",
            "Both profiles succeeded, but the available evidence does not establish an "
            "authorization failure.",
            differences,
            signals,
            False,
        )
    return ComparisonDecision(
        "ambiguous_result",
        "low",
        "informational",
        "The observations do not match a deterministic authorization rule. "
        "Manual review is required.",
        differences,
        signals,
        False,
    )
