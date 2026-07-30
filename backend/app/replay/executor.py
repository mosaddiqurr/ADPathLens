from __future__ import annotations

import ipaddress
import json
import re
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode, urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.problems import ApiProblem
from app.models import (
    ImportedRequest,
    Target,
    TargetAllowlistEntry,
    TestCase,
    TestCaseVariable,
    TestSession,
)
from app.replay.normalization import NormalizedResponse, normalize_response
from app.security.crypto import KeyRing, SecretEncryptionError
from app.security.ssrf import (
    AllowlistRule,
    DestinationPolicyError,
    normalize_url,
    resolve_all,
    validate_destination,
)
from app.services.request_policy import validate_request_policy

PLACEHOLDER = re.compile(r"\{\{([A-Za-z][A-Za-z0-9_]{0,79})\}\}")


class ReplayError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ReplayResult:
    status_code: int
    reason_phrase: str
    content_type: str | None
    final_url: str
    redirect_chain: list[dict[str, object]]
    elapsed_ms: float
    normalized: NormalizedResponse


@dataclass(frozen=True)
class StreamedResponse:
    status_code: int
    reason_phrase: str
    headers: list[tuple[str, str]]
    content_type: str | None
    location: str | None
    body: bytes


def _ring(settings: Settings) -> KeyRing:
    return KeyRing.from_settings(settings.encryption_master_key, settings.encryption_old_keys)


def _session_aad(session: TestSession, field: str) -> str:
    return f"test_session:{session.project_id}:{session.target_id}:{session.id}:{field}"


def _decrypt_optional(ring: KeyRing, value: bytes | None, associated_data: str) -> str | None:
    if value is None:
        return None
    try:
        return ring.decrypt(value, associated_data).decode()
    except (SecretEncryptionError, UnicodeDecodeError) as exc:
        raise ReplayError(
            "session_decryption_failed",
            "The selected session credentials could not be decrypted.",
        ) from exc


async def load_session_headers(
    session: TestSession,
    settings: Settings,
) -> list[tuple[str, str]]:
    if not session.is_active:
        raise ReplayError("session_revoked", "The selected session profile is revoked.")
    expires_at = session.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise ReplayError("session_expired", "The selected session profile has expired.")
    if session.is_anonymous:
        return []
    ring = _ring(settings)
    headers: list[tuple[str, str]] = []
    cookie = _decrypt_optional(
        ring,
        session.encrypted_cookie_data,
        _session_aad(session, "cookie"),
    )
    authorization = _decrypt_optional(
        ring,
        session.encrypted_authorization_header,
        _session_aad(session, "authorization"),
    )
    custom = _decrypt_optional(
        ring,
        session.encrypted_custom_headers,
        _session_aad(session, "custom_headers"),
    )
    if cookie:
        headers.append(("Cookie", cookie))
    if authorization:
        value = authorization
        if not value.lower().startswith(("bearer ", "basic ")):
            value = f"Bearer {value}"
        headers.append(("Authorization", value))
    if custom:
        try:
            values = json.loads(custom)
            headers.extend((str(name), str(value)) for name, value in values)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ReplayError(
                "session_decryption_failed",
                "The selected session credentials are malformed.",
            ) from exc
    return headers


async def _load_variables(
    db: AsyncSession,
    test_case: TestCase,
    scope: str,
    settings: Settings,
) -> dict[str, str]:
    rows = (
        (
            await db.execute(
                select(TestCaseVariable).where(
                    TestCaseVariable.test_case_id == test_case.id,
                    TestCaseVariable.scope.in_(["shared", scope]),
                )
            )
        )
        .scalars()
        .all()
    )
    ring = _ring(settings)
    result: dict[str, str] = {}
    for row in rows:
        try:
            result[row.name] = ring.decrypt(
                row.encrypted_value, f"test_case_variable:{row.id}:value"
            ).decode()
        except (SecretEncryptionError, UnicodeDecodeError) as exc:
            raise ReplayError(
                "variable_decryption_failed", "A request variable could not be decrypted."
            ) from exc
    return result


def render_template(value: str, variables: dict[str, str]) -> str:
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            missing.add(name)
            return match.group(0)
        return variables[name]

    rendered = PLACEHOLDER.sub(replace, value)
    if missing:
        names = ", ".join(sorted(missing))
        raise ReplayError("missing_variables", f"Required request variables are missing: {names}.")
    return rendered


async def _allowlist_rules(db: AsyncSession, target_id: str) -> list[AllowlistRule]:
    entries = (
        (
            await db.execute(
                select(TargetAllowlistEntry).where(TargetAllowlistEntry.target_id == target_id)
            )
        )
        .scalars()
        .all()
    )
    return [AllowlistRule(item.entry_type, item.value, item.allowed_port) for item in entries]


async def _validated_addresses(
    db: AsyncSession,
    target: Target,
    destination_url: str,
) -> list[str]:
    destination = normalize_url(destination_url)
    try:
        try:
            literal = ipaddress.ip_address(destination.hostname)
            resolved = [str(literal)]
        except ValueError:
            resolved = await resolve_all(destination.hostname, destination.port)
        return validate_destination(
            destination,
            resolved,
            target.hostname,
            target.port,
            await _allowlist_rules(db, target.id),
            authorization_confirmed=target.authorization_confirmed,
            allow_private_networks=target.allow_private_networks,
            lab_network_confirmed=target.lab_network_confirmed,
        )
    except DestinationPolicyError as exc:
        raise ReplayError(exc.code, exc.detail) from exc


def _host_header(target: Target) -> str:
    host = f"[{target.hostname}]" if ":" in target.hostname else target.hostname
    default = 443 if target.scheme == "https" else 80
    return host if target.port == default else f"{host}:{target.port}"


def _ssl_context(target: Target, settings: Settings) -> ssl.SSLContext | bool:
    if target.scheme != "https":
        return True
    if target.tls_policy == "custom_ca":
        if not settings.custom_ca_path:
            raise ReplayError(
                "custom_ca_missing", "The target requires a custom CA that is not configured."
            )
        return ssl.create_default_context(cafile=settings.custom_ca_path)
    return ssl.create_default_context()


async def _stream_once(
    client: httpx.AsyncClient,
    db: AsyncSession,
    *,
    target: Target,
    current_url: str,
    method: str,
    headers: list[tuple[str, str]],
    body: str,
    settings: Settings,
) -> StreamedResponse:
    addresses = await _validated_addresses(db, target, current_url)
    selected_ip = addresses[0]
    destination = normalize_url(current_url)
    connect_url = httpx.URL(current_url).copy_with(host=selected_ip)
    outbound = client.build_request(method, connect_url, headers=headers, content=body)
    outbound.extensions["sni_hostname"] = destination.hostname
    response = await client.send(outbound, stream=True)
    try:
        response_body = bytearray()
        async for chunk in response.aiter_bytes():
            response_body.extend(chunk)
            effective_limit = min(settings.max_response_bytes, target.maximum_response_bytes)
            if (
                len(response_body) > effective_limit
                or response.num_bytes_downloaded > effective_limit
            ):
                raise ReplayError(
                    "response_too_large",
                    "The target response exceeded the configured size limit.",
                )
            if (
                response.num_bytes_downloaded > 0
                and len(response_body) / response.num_bytes_downloaded
                > settings.max_decompression_ratio
            ):
                raise ReplayError(
                    "decompression_ratio_exceeded",
                    "The target response exceeded the decompression ratio limit.",
                )
        return StreamedResponse(
            status_code=response.status_code,
            reason_phrase=response.reason_phrase,
            headers=list(response.headers.multi_items()),
            content_type=response.headers.get("content-type"),
            location=response.headers.get("location"),
            body=bytes(response_body),
        )
    finally:
        await response.aclose()


def _translate_http_error(exc: httpx.HTTPError) -> ReplayError:
    if isinstance(exc, httpx.TimeoutException):
        return ReplayError("request_timeout", "The target request timed out.")
    if isinstance(exc, httpx.ConnectError):
        cause_text = str(exc).lower()
        if any(term in cause_text for term in ("ssl", "tls", "certificate")):
            return ReplayError("tls_failure", "TLS validation failed for the target.")
    return ReplayError("network_failure", "The target request failed at the network layer.")


async def execute_request(
    db: AsyncSession,
    *,
    test_case: TestCase,
    target: Target,
    request_definition: ImportedRequest,
    session: TestSession,
    scope: str,
    settings: Settings,
) -> ReplayResult:
    await db.refresh(target)
    try:
        validate_request_policy(
            target,
            method=request_definition.method,
            path=request_definition.path,
            approved_state_change=(
                request_definition.approved_state_change and test_case.approved_state_change
            ),
            require_active=True,
        )
    except ApiProblem as exc:
        raise ReplayError(exc.code, str(exc.detail)) from exc
    if target.request_count_used > target.request_budget:
        raise ReplayError(
            "target_request_budget_exhausted",
            "The target request budget was reduced below the reserved request count.",
        )
    if session.project_id != test_case.project_id or session.target_id != target.id:
        raise ReplayError(
            "session_scope_mismatch",
            "The selected session profile does not belong to this project and target.",
        )
    variables = await _load_variables(db, test_case, scope, settings)
    path = render_template(request_definition.path, variables)
    query = [
        (render_template(name, variables), render_template(value, variables))
        for name, value in request_definition.query_parameters
    ]
    query_string = urlencode(query, doseq=True)
    current_url = f"{target.base_url}{path}"
    if query_string:
        current_url = f"{current_url}?{query_string}"
    body = render_template(request_definition.body_template, variables)
    headers = [
        (name, render_template(value, variables))
        for name, value in request_definition.sanitized_headers
    ]
    session_headers = await load_session_headers(session, settings)
    session_names = {name.lower() for name, _ in session_headers}
    headers = [(name, value) for name, value in headers if name.lower() not in session_names]
    headers.extend(session_headers)
    headers.extend(
        [
            ("Host", _host_header(target)),
            ("Accept-Encoding", "identity"),
            ("User-Agent", "AuthZDiff/0.1 authorized-comparison"),
        ]
    )
    redirect_chain: list[dict[str, object]] = []
    method = request_definition.method
    started = time.perf_counter()
    max_hops = target.maximum_redirects if target.follow_redirects else 0
    verify = _ssl_context(target, settings)
    async with httpx.AsyncClient(
        verify=verify,
        timeout=httpx.Timeout(target.timeout_seconds),
        follow_redirects=False,
        trust_env=False,
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
    ) as client:
        for hop in range(max_hops + 1):
            # Only safe, read-only methods receive one transient network retry. DNS
            # policy is rerun inside _stream_once immediately before every attempt.
            attempt_limit = 2 if method in {"GET", "HEAD", "OPTIONS"} else 1
            streamed: StreamedResponse | None = None
            for attempt in range(attempt_limit):
                try:
                    streamed = await _stream_once(
                        client,
                        db,
                        target=target,
                        current_url=current_url,
                        method=method,
                        headers=headers,
                        body=body,
                        settings=settings,
                    )
                    break
                except ReplayError:
                    raise
                except httpx.HTTPError as exc:
                    if attempt + 1 < attempt_limit:
                        continue
                    raise _translate_http_error(exc) from exc
            if streamed is None:
                raise ReplayError(
                    "network_failure",
                    "The target request failed at the network layer.",
                )
            status = streamed.status_code
            reason = streamed.reason_phrase
            response_headers = streamed.headers
            content_type = streamed.content_type
            location = streamed.location
            response_body = streamed.body
            if status not in {301, 302, 303, 307, 308} or not location:
                normalized = normalize_response(
                    status_code=status,
                    headers=response_headers,
                    body=bytes(response_body),
                    content_type=content_type,
                    max_excerpt_bytes=settings.max_report_excerpt_bytes,
                    expected_markers=request_definition.expected_markers,
                )
                return ReplayResult(
                    status_code=status,
                    reason_phrase=reason,
                    content_type=content_type,
                    final_url=current_url,
                    redirect_chain=redirect_chain,
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                    normalized=normalized,
                )
            if hop >= max_hops:
                raise ReplayError(
                    "redirect_limit", "The response exceeded the target redirect policy."
                )
            next_url = urljoin(current_url, location)
            next_destination = normalize_url(next_url)
            await db.refresh(target)
            try:
                validate_request_policy(
                    target,
                    method=method,
                    path=next_destination.path,
                    approved_state_change=(
                        request_definition.approved_state_change and test_case.approved_state_change
                    ),
                    require_active=True,
                )
            except ApiProblem as exc:
                raise ReplayError(exc.code, str(exc.detail)) from exc
            if status == 303:
                if method not in {"GET", "HEAD"}:
                    raise ReplayError(
                        "unsafe_redirect_method_change",
                        "A redirect attempted to change a state-changing request method.",
                    )
                method = "GET"
                body = ""
            elif status in {301, 302} and method not in {"GET", "HEAD"}:
                raise ReplayError(
                    "unsafe_redirect_method_change",
                    "Automatic state-changing method conversion is not allowed.",
                )
            await _validated_addresses(db, target, next_url)
            redirect_chain.append({"status": status, "url": next_destination.url})
            current_url = next_url
    raise ReplayError("unexpected_execution_state", "The request did not produce a result.")
