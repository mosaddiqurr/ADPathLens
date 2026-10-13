"""Stateless local comparison API. No persistence, accounts, or outbound requests."""

from __future__ import annotations

import logging
from threading import BoundedSemaphore
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.comparison.states import compare
from app.core.config import get_settings
from app.core.problems import ApiProblem
from app.parsers.states import parse_input
from app.reporting.generator import render_csv, render_json, render_pdf
from app.schemas.comparison import CompareRequest, ComparisonResult, InputData, InputSummary

settings = get_settings()
slots = BoundedSemaphore(2)
logger = logging.getLogger("authzdiff")


class InputGuard:
    """Bound actual streamed bytes before JSON decoding, including chunked requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope["headers"]}
        origin = headers.get(b"origin", b"").decode("latin-1")
        if origin and origin not in settings.cors_origins:
            await self.reject(scope, receive, send, 403, "This origin is not allowed.")
            return
        if headers.get(b"content-type", b"").split(b";", 1)[0].strip() != b"application/json":
            await self.reject(scope, receive, send, 415, "Use a JSON request body.")
            return
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = settings.max_body_bytes + 1
        if length < 0 or length > settings.max_body_bytes:
            await self.reject(scope, receive, send, 413, "The request is too large.")
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > settings.max_body_bytes:
                await self.reject(scope, receive, send, 413, "The request is too large.")
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

    @staticmethod
    async def reject(scope: Scope, receive: Receive, send: Send, status: int, detail: str) -> None:
        response = JSONResponse(
            {"detail": detail},
            status_code=status,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
        await response(scope, receive, send)


app = FastAPI(title="AuthZDiff", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(InputGuard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)


@app.middleware("http")
async def privacy_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(ApiProblem)
async def problem_handler(_request: Request, exc: ApiProblem) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    return JSONResponse({"detail": "The input could not be parsed."}, status_code=422)


@app.exception_handler(HTTPException)
async def http_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        {"detail": "The request could not be completed."}, status_code=exc.status_code
    )


@app.exception_handler(Exception)
async def unexpected_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("Comparison request failed (%s)", type(exc).__name__)
    return JSONResponse(
        {"detail": "The request could not be completed."},
        status_code=500,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/v1/health")
@app.get("/api/v1/ready")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0", "processing": "memory-only"}


@app.post("/api/v1/inspect", response_model=InputSummary)
def inspect(data: InputData) -> InputSummary:
    if not slots.acquire(blocking=False):
        raise ApiProblem(429, "busy", "The comparison service is busy. Try again shortly.")
    try:
        return parse_input(data).summary
    finally:
        slots.release()


@app.post("/api/v1/compare", response_model=ComparisonResult)
def comparison(data: CompareRequest) -> ComparisonResult:
    if not slots.acquire(blocking=False):
        raise ApiProblem(429, "busy", "The comparison service is busy. Try again shortly.")
    try:
        return compare(data)
    finally:
        slots.release()


@app.post("/api/v1/reports/{output_format}")
def report(output_format: Literal["pdf", "json", "csv"], data: CompareRequest) -> Response:
    if not slots.acquire(blocking=False):
        raise ApiProblem(429, "busy", "The comparison service is busy. Try again shortly.")
    try:
        # Recompute from exact inputs: exports cannot invent or alter evidence.
        result = compare(data)
        if output_format == "pdf":
            content, media_type = render_pdf(result), "application/pdf"
        elif output_format == "csv":
            content, media_type = render_csv(result), "text/csv; charset=utf-8"
        else:
            content, media_type = render_json(result), "application/json"
        return Response(
            content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="authzdiff-report.{output_format}"',
                "Cache-Control": "no-store",
            },
        )
    finally:
        slots.release()
