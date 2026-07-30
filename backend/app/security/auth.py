from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import Settings


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session_material(settings: Settings) -> tuple[str, str, str, str, datetime]:
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.session_expiry_minutes)
    return raw_token, hash_token(raw_token), csrf_token, hash_token(csrf_token), expires_at


def issue_preauth_csrf(settings: Settings) -> str:
    nonce = secrets.token_urlsafe(24)
    timestamp = str(int(datetime.now(UTC).timestamp()))
    payload = f"{nonce}.{timestamp}"
    signature = hmac.new(
        settings.app_secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_preauth_csrf(settings: Settings, token: str, max_age_seconds: int = 600) -> bool:
    parts = token.split(".")
    if len(parts) != 3:
        return False
    payload = ".".join(parts[:2])
    expected = hmac.new(
        settings.app_secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, parts[2]):
        return False
    try:
        issued_at = datetime.fromtimestamp(int(parts[1]), tz=UTC)
    except (ValueError, OSError):
        return False
    age = datetime.now(UTC) - issued_at
    return timedelta(0) <= age <= timedelta(seconds=max_age_seconds)
