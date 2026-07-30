from __future__ import annotations

from datetime import UTC, datetime

from app.core.problems import ApiProblem
from app.models import Target


def path_allowed(path: str, prefixes: list[str]) -> bool:
    for prefix in prefixes:
        normalized = prefix.rstrip("/") or "/"
        if normalized == "/" or path == normalized or path.startswith(f"{normalized}/"):
            return True
    return False


def validate_request_policy(
    target: Target,
    *,
    method: str,
    path: str,
    approved_state_change: bool,
    require_active: bool = False,
) -> None:
    if require_active and not target.is_active:
        raise ApiProblem(403, "target_disabled", "The selected target is disabled.")
    expires_at = target.authorization_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise ApiProblem(
                403, "target_authorization_expired", "The target authorization has expired."
            )
    if method.upper() not in target.allowed_methods:
        raise ApiProblem(
            403, "method_not_allowed_by_target", "The request method is outside target policy."
        )
    if not path_allowed(path, target.allowed_path_prefixes):
        raise ApiProblem(
            403, "path_not_allowed_by_target", "The request path is outside target policy."
        )
    if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        if not target.state_changes_enabled or not approved_state_change:
            raise ApiProblem(
                403,
                "state_change_not_approved",
                "State-changing requests require both target and request approval.",
            )
