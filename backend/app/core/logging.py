from __future__ import annotations

import logging
import sys
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any, cast

import structlog

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "password",
    "secret",
    "token",
    "csrf",
    "api_key",
    "api-key",
}


def redact(value: Any, key: str | None = None) -> Any:
    if key and any(marker in key.lower() for marker in SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(item_key): redact(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [redact(item) for item in value]
    return value


def _redaction_processor(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    return cast(MutableMapping[str, Any], redact(event_dict))


def configure_logging(level: str) -> None:
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _redaction_processor,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
