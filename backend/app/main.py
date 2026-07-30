from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.problems import ApiProblem
from app.services.coordinator import coordinator

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings.report_storage_path.mkdir(parents=True, exist_ok=True)
    if settings.replay_execution_mode == "inprocess":
        await coordinator.recover_interrupted(include_queued=True)
    logger.info("application_started", version=settings.app_version, environment=settings.app_env)
    yield
    logger.info("application_stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.clear_contextvars()
    response.headers["X-Request-ID"] = request_id
    return response


def _problem_response(
    request: Request,
    status: int,
    code: str,
    detail: str,
    *,
    field_errors: list[dict[str, object]] | None = None,
) -> JSONResponse:
    content: dict[str, object] = {
        "type": "about:blank",
        "title": "Request failed" if status < 500 else "Internal server error",
        "status": status,
        "code": code,
        "detail": detail,
        "instance": request.url.path,
        "request_id": getattr(request.state, "request_id", None),
    }
    if field_errors is not None:
        content["field_errors"] = field_errors
    return JSONResponse(status_code=status, media_type="application/problem+json", content=content)


@app.exception_handler(ApiProblem)
async def api_problem_handler(request: Request, exc: ApiProblem) -> JSONResponse:
    return _problem_response(request, exc.status_code, exc.code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [
        {
            "location": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return _problem_response(
        request,
        422,
        "validation_error",
        "One or more request fields are invalid.",
        field_errors=fields,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return _problem_response(
        request,
        exc.status_code,
        "http_error",
        str(exc.detail),
    )


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        path=request.url.path,
        exception_type=type(exc).__name__,
    )
    return _problem_response(
        request,
        500,
        "internal_error",
        "The request could not be completed.",
    )


app.include_router(api_router, prefix="/api/v1")
