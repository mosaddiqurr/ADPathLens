from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        *,
        code: str = "application_error",
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.code = code
        self.extra = extra or {}
        super().__init__(detail)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    response = JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content={
            "type": f"https://adpathlens.local/problems/{exc.code}",
            "title": exc.title,
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": str(request.url.path),
            "code": exc.code,
            "request_id": getattr(request.state, "request_id", None),
            **exc.extra,
        },
    )
    return response


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {
            "location": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "code": error["type"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        media_type="application/problem+json",
        content={
            "type": "https://adpathlens.local/problems/validation_error",
            "title": "Request validation failed",
            "status": 422,
            "detail": "One or more request fields are invalid.",
            "instance": str(request.url.path),
            "code": "validation_error",
            "request_id": getattr(request.state, "request_id", None),
            "errors": errors,
        },
    )


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content={
            "type": "https://adpathlens.local/problems/http_error",
            "title": "Request failed",
            "status": exc.status_code,
            "detail": detail,
            "instance": str(request.url.path),
            "code": "http_error",
            "request_id": getattr(request.state, "request_id", None),
        },
        headers=exc.headers,
    )


async def unhandled_error_handler(request: Request, _: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        media_type="application/problem+json",
        content={
            "type": "https://adpathlens.local/problems/internal_error",
            "title": "Internal server error",
            "status": 500,
            "detail": "The request could not be completed.",
            "instance": str(request.url.path),
            "code": "internal_error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )
