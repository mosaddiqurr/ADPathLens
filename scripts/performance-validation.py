from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.comparison.engine import compare_observations  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models import Finding, ImportedRequest, Observation  # noqa: E402
from app.replay.normalization import normalize_response  # noqa: E402
from app.reporting.generator import render_csv, render_html, render_json, render_pdf  # noqa: E402

REQUEST_COUNT = 100
OBSERVATION_COUNT = 1_000
COMPARISON_COUNT = OBSERVATION_COUNT // 2
FINDING_COUNT = 100


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1_000, 2)


async def validate() -> dict[str, object]:
    output_dir = Path(
        os.environ.get(
            "AUTHZDIFF_PERFORMANCE_DIR", ROOT / "var" / "performance-validation"
        )
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    database = output_dir / "performance.sqlite"
    pdf_path = output_dir / "performance-report.pdf"
    for path in (database, pdf_path):
        if path.exists():
            path.unlink()

    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    timings: dict[str, float] = {}
    project_id = "performance-project"
    user_id = "performance-user"
    target_id = "performance-target"

    started = time.perf_counter()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    timings["schema_create_ms"] = elapsed_ms(started)

    requests = [
        ImportedRequest(
            project_id=project_id,
            target_id=target_id,
            name=f"Synthetic request {index:03d}",
            import_type="manual",
            method="GET",
            scheme="https",
            hostname="fixture.invalid",
            port=443,
            path=f"/fixture/{index:03d}",
            query_parameters=[],
            sanitized_headers=[],
            content_type=None,
            body_template="",
            body_hash=hashlib.sha256(b"").hexdigest(),
            is_state_changing=False,
            approved_state_change=False,
            expected_markers=[],
            tags=["performance"],
            sensitivity="internal",
            created_by=user_id,
        )
        for index in range(REQUEST_COUNT)
    ]
    started = time.perf_counter()
    async with sessions() as db:
        db.add_all(requests)
        await db.commit()
    timings["persist_100_requests_ms"] = elapsed_ms(started)

    observations: list[Observation] = []
    started = time.perf_counter()
    for index in range(OBSERVATION_COUNT):
        body = json.dumps(
            {
                "fixture": "bounded-performance",
                "record": index % 100,
                "owner_id": f"user-{index % 10}",
                "email": f"user-{index % 10}@example.invalid",
                "request_id": f"volatile-{index}",
            },
            separators=(",", ":"),
        ).encode()
        normalized = normalize_response(
            status_code=200,
            headers=[
                ("Content-Type", "application/json"),
                ("X-Request-ID", str(index)),
            ],
            body=body,
            content_type="application/json",
            max_excerpt_bytes=100 * 1024,
            expected_markers=["bounded-performance"],
            redaction_paths=["$.request_id"],
        )
        observations.append(
            Observation(
                project_id=project_id,
                comparison_run_id=f"run-{index:04d}",
                request_id=requests[index % REQUEST_COUNT].id,
                session_id=f"session-{index:04d}",
                status_code=200,
                redirect_outcome="not_followed",
                content_type="application/json",
                safe_headers=normalized.safe_headers,
                response_length=normalized.response_length,
                duration_ms=5.0 + (index % 7),
                json_shape=normalized.json_shape,
                top_level_json_keys=normalized.top_level_keys,
                structural_representation=normalized.structural,
                sanitized_body_hash=normalized.body_hash,
                sanitized_excerpt=normalized.excerpt,
                error_category=None,
                auth_challenge=normalized.auth_challenge,
                access_denied_marker=normalized.denied,
                object_existence_marker=normalized.object_marker,
                success_markers=normalized.success_markers,
                body_truncated=normalized.truncated,
                is_binary=normalized.binary,
            )
        )
    timings["normalize_1000_observations_ms"] = elapsed_ms(started)

    started = time.perf_counter()
    async with sessions() as db:
        db.add_all(observations)
        await db.commit()
    timings["persist_1000_observations_ms"] = elapsed_ms(started)

    started = time.perf_counter()
    candidates = 0
    for index in range(0, OBSERVATION_COUNT, 2):
        decision = compare_observations(
            observations[index],
            observations[index + 1],
            expected_behaviour="ownership_separation",
            is_state_changing=False,
        )
        candidates += int(decision.candidate)
    timings["compare_500_pairs_ms"] = elapsed_ms(started)

    now = datetime.now(UTC)
    findings = [
        Finding(
            project_id=project_id,
            comparison_run_id=f"finding-run-{index:03d}",
            fingerprint=hashlib.sha256(f"finding-{index}".encode()).hexdigest(),
            title=f"Synthetic candidate {index:03d}",
            category="potential_horizontal_authorization_issue",
            severity="medium",
            confidence="medium",
            status="candidate",
            target_snapshot="https://fixture.invalid",
            endpoint_snapshot=f"/fixture/{index:03d}",
            expected_behaviour="ownership_separation",
            observed_behaviour="Synthetic deterministic comparison candidate.",
            description="Bounded performance fixture.",
            impact="Manual assessment required.",
            reproduction_summary="Synthetic fixture only.",
            remediation="Enforce object ownership on the server.",
            reviewer_notes="",
            priority="normal",
            tags=["performance"],
            redaction_summary="Reusable credentials excluded.",
            limitations="Synthetic measurement.",
            created_by=user_id,
            first_seen_at=now,
            last_seen_at=now,
            recurrence_count=1,
        )
        for index in range(FINDING_COUNT)
    ]
    started = time.perf_counter()
    async with sessions() as db:
        db.add_all(findings)
        await db.commit()
    timings["persist_100_findings_ms"] = elapsed_ms(started)

    started = time.perf_counter()
    async with sessions() as db:
        observation_total = (
            await db.execute(
                select(func.count(Observation.id)).where(
                    Observation.project_id == project_id,
                    Observation.status_code == 200,
                )
            )
        ).scalar_one()
        finding_total = (
            await db.execute(
                select(func.count(Finding.id)).where(
                    Finding.project_id == project_id,
                    Finding.status == "candidate",
                    Finding.severity == "medium",
                )
            )
        ).scalar_one()
    timings["search_and_filter_ms"] = elapsed_ms(started)

    payload: dict[str, object] = {
        "project": {"name": "Performance fixture"},
        "generated_at": now.isoformat(),
        "content_hash": hashlib.sha256(b"performance-fixture").hexdigest(),
        "redaction_summary": "Reusable credentials excluded.",
        "limitations": "Synthetic bounded performance workload.",
        "findings": [
            {
                "title": finding.title,
                "category": finding.category,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "status": finding.status,
                "target": finding.target_snapshot,
                "endpoint": finding.endpoint_snapshot,
                "description": finding.description,
                "remediation": finding.remediation,
            }
            for finding in findings
        ],
    }
    started = time.perf_counter()
    rendered = {
        "json": len(render_json(payload)),
        "csv": len(render_csv(payload)),
        "html": len(render_html(payload)),
    }
    render_pdf(payload, pdf_path)
    rendered["pdf"] = pdf_path.stat().st_size
    timings["render_four_reports_ms"] = elapsed_ms(started)

    await engine.dispose()
    _current, peak = tracemalloc.get_traced_memory()
    return {
        "workload": {
            "requests": REQUEST_COUNT,
            "observations": OBSERVATION_COUNT,
            "comparisons": COMPARISON_COUNT,
            "findings": FINDING_COUNT,
        },
        "verified_counts": {
            "observations": observation_total,
            "filtered_findings": finding_total,
            "comparison_candidates": candidates,
        },
        "timings": timings,
        "database_bytes": database.stat().st_size,
        "report_bytes": rendered,
        "peak_traced_memory_bytes": peak,
    }


def main() -> None:
    tracemalloc.start()
    print(json.dumps(asyncio.run(validate()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
