"""Bounded, offline imports. Uploaded filenames and URLs are never opened."""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import ValidationError

from app.comparison.normalization import (
    normalize_response,
    redact_text,
    sensitive_field,
)
from app.comparison.observations import Observation
from app.core.problems import ApiProblem
from app.parsers.request_import import (
    HEADER_NAME,
    RequestImportError,
    canonicalize_path,
    json_nesting_depth,
    validate_method,
)
from app.schemas.comparison import PUBLIC_NAMES, AccessRecord, InputData, InputSummary

MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 2000
MAX_HAR_ENTRIES = 500
MAX_CAPTURE_BODY = 256 * 1024
MAX_EXCERPT = 8000
FIELDS = {"principal", "resource", "action", "effect", "role", "sensitive"}
REQUIRED_FIELDS = {"principal", "resource", "action", "effect"}


@dataclass(frozen=True)
class CaptureRecord:
    key: tuple[str, str, str, str]
    principal: str
    resource: str
    action: str
    access: Literal["allowed", "denied", "unknown"]
    sensitive: bool
    observation: Observation
    evidence: dict[str, Any]


@dataclass(frozen=True)
class Dataset:
    summary: InputSummary
    records: list[AccessRecord] | list[CaptureRecord]


def _invalid(side: str) -> ApiProblem:
    return ApiProblem(422, "invalid_input", f"The {side} dataset could not be parsed.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON member")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError("Non-finite JSON number")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite JSON number")
    return result


def bounded_json(text: str) -> Any:
    # Check depth before json.loads can recurse. Quoted brackets do not count.
    depth = 0
    quoted = escaped = False
    nodes = 0
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            nodes += 1
            if depth > 30 or nodes > 50_000:
                raise ValueError("JSON structure limit")
        elif char in "]}":
            depth -= 1
    return json.loads(
        text,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
        parse_float=_finite_float,
    )


def _snapshot_rows(document: Any) -> list[Any]:
    if isinstance(document, list):
        return document
    if not isinstance(document, dict) or "records" not in document:
        raise ApiProblem(415, "unsupported_input", "This file format is not supported.")
    if set(document) - {"schema", "name", "records"}:
        raise ValueError("Unknown snapshot fields")
    if document.get("schema", "authzdiff/snapshot-v1") != "authzdiff/snapshot-v1":
        raise ApiProblem(415, "unsupported_input", "This file format is not supported.")
    if not isinstance(document["records"], list):
        raise ValueError("Records must be an array")
    return document["records"]


def _csv_rows(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    headers = reader.fieldnames or []
    if len(set(headers)) != len(headers) or not REQUIRED_FIELDS <= set(headers):
        raise ValueError("Required CSV columns are missing or duplicated")
    if set(headers) - FIELDS:
        raise ValueError("Unknown CSV columns")
    rows: list[dict[str, Any]] = []
    for row in reader:
        if len(rows) >= MAX_RECORDS or None in row or any(v is None for v in row.values()):
            raise ValueError("CSV row or record limit")
        normalized: dict[str, Any] = dict(row)
        if "sensitive" in normalized:
            flag = normalized["sensitive"].strip().casefold()
            if flag not in {"true", "false", ""}:
                raise ValueError("Invalid sensitivity flag")
            normalized["sensitive"] = flag == "true"
        if normalized.get("role") == "":
            normalized.pop("role")
        rows.append(normalized)
    return rows


def _snapshot(rows: list[Any]) -> list[AccessRecord]:
    if len(rows) > MAX_RECORDS:
        raise ValueError("Snapshot record limit")
    records = [AccessRecord.model_validate(row) for row in rows]
    if len({record.key for record in records}) != len(records):
        raise ValueError("Duplicate principal/resource/action tuple")
    return records


def _annotation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - {"principal", "access", "sensitive"}:
        raise ValueError("Invalid capture context")
    if "principal" in value:
        # Reuse snapshot label validation without retaining arbitrary metadata.
        record = AccessRecord(
            principal=value["principal"], resource="capture", action="GET", effect="allow"
        )
        value = {**value, "principal": record.principal}
    if value.get("access", "unknown") not in {"allowed", "denied", "unknown"}:
        raise ValueError("Invalid access annotation")
    if "sensitive" in value and type(value["sensitive"]) is not bool:
        raise ValueError("Invalid sensitivity annotation")
    return dict(value)


def _capture_url(raw: Any) -> tuple[str, list[tuple[str, str]]]:
    if not isinstance(raw, str) or len(raw) > 4096 or any(ord(c) < 32 for c in raw):
        raise ValueError("Invalid capture URL")
    url = urlsplit(raw)
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.fragment
    ):
        raise ValueError("Invalid capture origin")
    host = url.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    port = url.port
    if ":" in host:
        host = f"[{host}]"
    origin = f"{url.scheme}://{host}"
    if port is not None and port != (443 if url.scheme == "https" else 80):
        origin += f":{port}"
    path = url.path or "/"
    canonicalize_path(path)  # Validate decoding without collapsing distinct request targets.
    # Query values can identify different objects. Credentials never identify a resource.
    query = [
        (key, value)
        for key, value in parse_qsl(url.query, keep_blank_values=True, max_num_fields=100)
        if not sensitive_field(key)
    ]
    return origin + path, sorted(query)


def _har(document: dict[str, Any]) -> tuple[list[CaptureRecord], list[str]]:
    log = document["log"]
    if not isinstance(log, dict) or not isinstance(log.get("entries"), list):
        raise ValueError("Missing HAR entries")
    entries = log["entries"]
    if len(entries) > MAX_HAR_ENTRIES:
        raise ValueError("HAR entry limit")
    context = _annotation(log.get("_authzdiff", {}))
    records: list[CaptureRecord] = []
    warnings: set[str] = set()
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError("Invalid HAR entry")
        request, response = entry.get("request"), entry.get("response")
        if not isinstance(request, dict) or not isinstance(response, dict):
            raise ValueError("Missing HAR request or response")
        resource, query = _capture_url(request.get("url"))
        method = validate_method(request.get("method", ""))
        annotation = {**context, **_annotation(entry.get("_authzdiff", {}))}
        principal = annotation.get("principal", "Unknown")
        if principal.casefold() in PUBLIC_NAMES:
            principal = "Public"
        status = response.get("status")
        if type(status) is not int or not (status == 0 or 100 <= status <= 599):
            raise ValueError("Invalid HAR status")
        content = response.get("content", {})
        if not isinstance(content, dict):
            raise ValueError("Invalid HAR response content")
        text = content.get("text", "")
        if not isinstance(text, str) or len(text.encode()) > MAX_CAPTURE_BODY * 4 // 3 + 4:
            raise ValueError("Capture body limit")
        encoding = content.get("encoding")
        if encoding not in {None, "base64"}:
            raise ValueError("Unsupported HAR encoding")
        body = base64.b64decode(text, validate=True) if encoding == "base64" else text.encode()
        if len(body) > MAX_CAPTURE_BODY:
            raise ValueError("Capture body limit")
        content_type = content.get("mimeType", "")
        if not isinstance(content_type, str) or len(content_type) > 256:
            raise ValueError("Invalid content type")
        if "json" in content_type.lower() and body:
            # Validate before recursively redacting or describing the JSON structure.
            parsed = bounded_json(body.decode("utf-8"))
            if json_nesting_depth(parsed) > 30:
                raise ValueError("Response depth limit")
        raw_headers = response.get("headers", [])
        if not isinstance(raw_headers, list) or len(raw_headers) > 100:
            raise ValueError("Invalid response headers")
        headers: list[tuple[str, str]] = []
        for header in raw_headers:
            if not isinstance(header, dict):
                raise ValueError("Invalid response header")
            name, value = header.get("name"), header.get("value")
            if not isinstance(name, str) or not isinstance(value, str):
                raise ValueError("Invalid response header")
            if len(name) > 128 or len(value) > 4096 or "\r" in value or "\n" in value:
                raise ValueError("Invalid response header")
            headers.append((name, value))
        truncated = entry.get("_truncated", False)
        if type(truncated) is not bool:
            raise ValueError("Invalid truncation flag")
        size = content.get("size", -1)
        if type(size) is not int or size < -1:
            raise ValueError("Invalid capture content size")
        truncated = truncated or size > len(body)
        normalized = normalize_response(
            status_code=status,
            headers=headers,
            body=body,
            content_type=content_type,
            max_excerpt_bytes=MAX_EXCERPT,
            expected_markers=[],
            truncated=truncated,
        )
        access = annotation.get("access", "unknown")
        corroborated = (access == "allowed" and 200 <= status < 300 and not normalized.denied) or (
            access == "denied" and normalized.denied
        )
        if (
            not annotation.get("principal")
            or not corroborated
            or normalized.truncated
            or status == 0
        ):
            access = "unknown"
            warnings.add("Some responses lack reliable authorization context and need review.")
        observation = Observation(
            status_code=status,
            response_length=normalized.response_length,
            sanitized_excerpt=normalized.excerpt,
            sanitized_body_hash=normalized.body_hash,
            structural_representation=normalized.structural,
            access_denied_marker=normalized.denied,
            error_category="capture_failed" if status == 0 else None,
            body_truncated=normalized.truncated,
            redirect_outcome="redirect" if 300 <= status < 400 else "none",
            safe_headers=normalized.safe_headers,
            content_type=redact_text(content_type),
        )
        # Hash complete request context; never export request headers/bodies/raw queries.
        request_headers = request.get("headers", [])
        if not isinstance(request_headers, list) or len(request_headers) > 100:
            raise ValueError("Invalid request headers")
        context_headers = []
        for header in request_headers:
            if not isinstance(header, dict):
                raise ValueError("Invalid request header")
            name, value = header.get("name"), header.get("value")
            if (
                not isinstance(name, str)
                or not HEADER_NAME.fullmatch(name)
                or len(name) > 128
                or not isinstance(value, str)
                or len(value) > 4096
                or "\r" in value
                or "\n" in value
            ):
                raise ValueError("Invalid request header")
            if not sensitive_field(name):
                context_headers.append((name.casefold(), value))
        post_data = request.get("postData", {}) or {}
        if not isinstance(post_data, dict):
            raise ValueError("Invalid HAR request body")
        request_text = post_data.get("text", "")
        if not isinstance(request_text, str) or len(request_text.encode()) > MAX_CAPTURE_BODY:
            raise ValueError("Request body limit")
        mime_type = post_data.get("mimeType", "")
        params = post_data.get("params", [])
        if not isinstance(mime_type, str) or len(mime_type) > 256:
            raise ValueError("Invalid request content type")
        if not isinstance(params, list) or len(params) > 1000:
            raise ValueError("Invalid request parameters")
        for param in params:
            if (
                not isinstance(param, dict)
                or not isinstance(param.get("name"), str)
                or not isinstance(param.get("value", ""), str)
                or set(param) - {"name", "value", "fileName", "contentType", "comment"}
                or any(not isinstance(value, str) for value in param.values())
            ):
                raise ValueError("Invalid request parameter")
        body_context = json.dumps(
            [mime_type, request_text, params], sort_keys=True, ensure_ascii=False
        )
        if len(body_context.encode()) > MAX_CAPTURE_BODY:
            raise ValueError("Request body limit")
        identity = json.dumps(
            [query, sorted(context_headers), body_context], sort_keys=True, ensure_ascii=False
        )
        key = (principal, resource, method, hashlib.sha256(identity.encode()).hexdigest())
        records.append(
            CaptureRecord(
                key=key,
                principal=principal,
                resource=resource,
                action=method,
                access=access,
                sensitive=annotation.get("sensitive", False),
                observation=observation,
                evidence={
                    "entry": index,
                    "status": status,
                    "access_context": access,
                    "content_type": redact_text(content_type),
                    "safe_headers": normalized.safe_headers,
                    "excerpt": normalized.excerpt,
                    "truncated": normalized.truncated,
                },
            )
        )
    if len({record.key for record in records}) != len(records):
        raise ValueError("Repeated capture requests are ambiguous; provide one per context")
    return records, sorted(warnings)


def parse_input(data: InputData, side: str = "input") -> Dataset:
    try:
        size = len(data.content.encode("utf-8"))
    except UnicodeError as exc:
        raise _invalid(side) from exc
    if size > MAX_INPUT_BYTES:
        raise ApiProblem(413, "input_too_large", "Each input must be 5 MB or smaller.")
    suffix = data.filename.rsplit(".", 1)[-1].lower()
    if suffix not in {"json", "csv", "har"}:
        raise ApiProblem(415, "unsupported_input", "This file format is not supported.")
    text = data.content.lstrip("\ufeff")
    try:
        warnings: list[str] = []
        input_format: Literal["snapshot", "har"]
        records: list[AccessRecord] | list[CaptureRecord]
        if suffix == "csv":
            records = _snapshot(_csv_rows(text))
            input_format, label = "snapshot", "Access snapshot · CSV"
        else:
            document = bounded_json(text)
            if isinstance(document, dict) and "log" in document:
                records, warnings = _har(document)
                input_format, label = "har", "HTTP capture · HAR"
            else:
                if suffix == "har":
                    raise ValueError("HAR log missing")
                records = _snapshot(_snapshot_rows(document))
                input_format, label = "snapshot", "Access snapshot · JSON"
        if not records:
            raise ApiProblem(422, "empty_input", "No comparable authorization records were found.")
        return Dataset(
            InputSummary(
                filename=redact_text(data.filename),
                format=input_format,
                format_label=label,
                record_count=len(records),
                warnings=warnings,
            ),
            records,
        )
    except ApiProblem:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        csv.Error,
        binascii.Error,
        ValidationError,
        RequestImportError,
    ) as exc:
        raise _invalid(side) from exc
