from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.models import ImportedRequest, Target
from app.models import TestCase as CaseModel
from app.models import TestSession as SessionModel
from app.replay import executor
from app.replay.executor import ReplayError, StreamedResponse, execute_request


class FakeDatabase:
    async def refresh(self, _value: object) -> None:
        return None


def _objects(method: str) -> tuple[CaseModel, Target, ImportedRequest, SessionModel]:
    target = Target(
        id="target",
        project_id="project",
        base_url="https://example.com",
        hostname="example.com",
        port=443,
        scheme="https",
        timeout_seconds=1,
        per_run_timeout_seconds=5,
        request_budget=10,
        request_count_used=2,
        maximum_response_bytes=2 * 1024 * 1024,
        maximum_redirects=0,
        follow_redirects=False,
        tls_policy="strict",
        allowed_methods=[method],
        allowed_path_prefixes=["/"],
        state_changes_enabled=method == "POST",
        is_active=True,
    )
    request = ImportedRequest(
        id="request",
        project_id="project",
        target_id="target",
        method=method,
        path="/fixture",
        query_parameters=[],
        sanitized_headers=[],
        body_template="",
        approved_state_change=method == "POST",
        expected_markers=[],
        is_state_changing=method == "POST",
    )
    test_case = CaseModel(
        id="case",
        project_id="project",
        target_id="target",
        imported_request_id="request",
        approved_state_change=method == "POST",
    )
    session = SessionModel(
        id="session",
        project_id="project",
        target_id="target",
        is_active=True,
        is_anonymous=True,
    )
    return test_case, target, request, session


@pytest.mark.asyncio
async def test_read_only_network_failure_receives_one_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def no_variables(*_args: Any, **_kwargs: Any) -> dict[str, str]:
        return {}

    async def transient(*_args: Any, **_kwargs: Any) -> StreamedResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("synthetic connection failure")
        return StreamedResponse(
            status_code=200,
            reason_phrase="OK",
            headers=[("Content-Type", "application/json")],
            content_type="application/json",
            location=None,
            body=b'{"status":"ok"}',
        )

    monkeypatch.setattr(executor, "_load_variables", no_variables)
    monkeypatch.setattr(executor, "_stream_once", transient)
    test_case, target, request, session = _objects("GET")
    result = await execute_request(
        FakeDatabase(),  # type: ignore[arg-type]
        test_case=test_case,
        target=target,
        request_definition=request,
        session=session,
        scope="low",
        settings=Settings(),
    )
    assert result.status_code == 200
    assert calls == 2


@pytest.mark.asyncio
async def test_state_changing_network_failure_is_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def no_variables(*_args: Any, **_kwargs: Any) -> dict[str, str]:
        return {}

    async def failure(*_args: Any, **_kwargs: Any) -> StreamedResponse:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("synthetic connection failure")

    monkeypatch.setattr(executor, "_load_variables", no_variables)
    monkeypatch.setattr(executor, "_stream_once", failure)
    test_case, target, request, session = _objects("POST")
    with pytest.raises(ReplayError) as caught:
        await execute_request(
            FakeDatabase(),  # type: ignore[arg-type]
            test_case=test_case,
            target=target,
            request_definition=request,
            session=session,
            scope="low",
            settings=Settings(),
        )
    assert caught.value.code == "network_failure"
    assert calls == 1
