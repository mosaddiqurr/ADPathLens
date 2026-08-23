from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

SENSITIVE_FIELD_NAMES = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "session",
    "session_id",
    "csrf",
    "ssn",
    "national_id",
    "private_key",
    "credit_card",
}
SAFE_RESPONSE_HEADERS = {
    "content-type",
    "content-language",
    "cache-control",
    "allow",
    "location",
    "www-authenticate",
    "x-content-type-options",
}
TOKEN_PATTERN = re.compile(
    r"(?i)(?:\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{4,}"
    r"|\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"
    r"|\b[A-Za-z0-9_-]{32,}\b)"
)


@dataclass(frozen=True)
class NormalizedResponse:
    safe_headers: list[list[str]]
    response_length: int
    json_shape: dict[str, Any] | None
    top_level_keys: list[str]
    structural: dict[str, Any] | list[Any] | None
    body_hash: str
    excerpt: str | None
    auth_challenge: bool
    denied: bool
    object_marker: bool
    success_markers: list[str]
    truncated: bool
    binary: bool


def _path_matches(path: str, patterns: list[str]) -> bool:
    return any(path == pattern or path.startswith(f"{pattern}.") for pattern in patterns)


def redact_json(
    value: Any,
    *,
    path: str = "$",
    redaction_paths: list[str] | None = None,
    redaction_keys: list[str] | None = None,
) -> Any:
    redaction_paths = redaction_paths or []
    configured_keys = {key.strip().lower() for key in (redaction_keys or []) if key.strip()}
    if _path_matches(path, redaction_paths):
        return "[REDACTED]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if (
                key.lower() in SENSITIVE_FIELD_NAMES
                or key.lower() in configured_keys
                or _path_matches(child_path, redaction_paths)
            ):
                result[key] = "[REDACTED]"
            else:
                result[key] = redact_json(
                    item,
                    path=child_path,
                    redaction_paths=redaction_paths,
                    redaction_keys=list(configured_keys),
                )
        return result
    if isinstance(value, list):
        return [
            redact_json(
                item,
                path=f"{path}[]",
                redaction_paths=redaction_paths,
                redaction_keys=list(configured_keys),
            )
            for item in value[:100]
        ]
    if isinstance(value, str):
        return TOKEN_PATTERN.sub("[REDACTED]", value)
    return value


def json_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        shapes = [json_shape(item) for item in value[:20]]
        unique = []
        for shape in shapes:
            if shape not in unique:
                unique.append(shape)
        return {"type": "array", "item_shapes": unique}
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    return "string"


def _safe_headers(headers: list[tuple[str, str]]) -> list[list[str]]:
    result: list[list[str]] = []
    for name, value in headers:
        lowered = name.lower()
        if lowered not in SAFE_RESPONSE_HEADERS:
            continue
        if lowered == "www-authenticate":
            value = value.split(maxsplit=1)[0]
        if lowered == "location":
            value = value.split("?", 1)[0]
        result.append([lowered, TOKEN_PATTERN.sub("[REDACTED]", value)[:2048]])
    return result


def normalize_response(
    *,
    status_code: int,
    headers: list[tuple[str, str]],
    body: bytes,
    content_type: str | None,
    max_excerpt_bytes: int,
    expected_markers: list[str],
    redaction_paths: list[str] | None = None,
    redaction_keys: list[str] | None = None,
    truncated: bool = False,
) -> NormalizedResponse:
    lowered_type = (content_type or "").lower()
    is_binary = (
        any(lowered_type.startswith(prefix) for prefix in ("image/", "audio/", "video/", "font/"))
        or "application/octet-stream" in lowered_type
        or b"\x00" in body[:1024]
    )
    if is_binary:
        safe = _safe_headers(headers)
        return NormalizedResponse(
            safe_headers=safe,
            response_length=len(body),
            json_shape=None,
            top_level_keys=[],
            structural=None,
            body_hash=hashlib.sha256(body).hexdigest(),
            excerpt=None,
            auth_challenge=status_code == 401
            or any(name == "www-authenticate" for name, _ in safe),
            denied=status_code in {401, 403},
            object_marker=status_code == 404,
            success_markers=[],
            truncated=truncated,
            binary=True,
        )
    text = body.decode("utf-8", errors="replace")
    structural: dict[str, Any] | list[Any] | None = None
    shape: dict[str, Any] | None = None
    top_keys: list[str] = []
    excerpt: str | None
    if content_type and "json" in content_type.lower():
        try:
            parsed = json.loads(text)
            redacted = redact_json(
                parsed,
                redaction_paths=redaction_paths,
                redaction_keys=redaction_keys,
            )
            structural = redacted if isinstance(redacted, dict | list) else {"value": redacted}
            computed_shape = json_shape(redacted)
            shape = computed_shape if isinstance(computed_shape, dict) else {"$": computed_shape}
            top_keys = sorted(redacted) if isinstance(redacted, dict) else []
            text = json.dumps(redacted, sort_keys=True, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            text = TOKEN_PATTERN.sub("[REDACTED]", text)
    elif content_type and "html" in content_type.lower():
        soup = BeautifulSoup(text, "html.parser")
        for node in soup(["script", "style", "template", "noscript"]):
            node.decompose()
        text = " ".join(soup.stripped_strings)
        text = TOKEN_PATTERN.sub("[REDACTED]", text)
    else:
        text = TOKEN_PATTERN.sub("[REDACTED]", text)
    excerpt_bytes = text.encode()[:max_excerpt_bytes]
    excerpt = excerpt_bytes.decode("utf-8", errors="ignore") if excerpt_bytes else None
    normalized_hash = hashlib.sha256(text.encode()).hexdigest()
    lower = text.lower()
    denied = status_code in {401, 403} or any(
        marker in lower for marker in ("access denied", "forbidden", "not authorized")
    )
    object_marker = status_code == 404 or "not found" in lower
    matched = [marker for marker in expected_markers if marker.lower() in lower]
    safe = _safe_headers(headers)
    challenge = status_code == 401 or any(name == "www-authenticate" for name, _ in safe)
    return NormalizedResponse(
        safe_headers=safe,
        response_length=len(body),
        json_shape=shape,
        top_level_keys=top_keys,
        structural=structural,
        body_hash=normalized_hash,
        excerpt=excerpt,
        auth_challenge=challenge,
        denied=denied,
        object_marker=object_marker,
        success_markers=matched,
        truncated=truncated,
        binary=False,
    )
