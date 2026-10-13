"""Database-independent observations for the proven response comparison rules."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Observation:
    status_code: int | None = None
    response_length: int = 0
    sanitized_excerpt: str | None = None
    sanitized_body_hash: str = ""
    structural_representation: dict[str, Any] | list[Any] | None = None
    access_denied_marker: bool = False
    error_category: str | None = None
    body_truncated: bool = False
    redirect_outcome: str = "none"
    safe_headers: list[list[str]] = field(default_factory=list)
    content_type: str | None = None
