"""Every non-2xx response uses the contract error shape (contracts/api.md §1)."""

from collections.abc import Sequence
from http import HTTPStatus
from typing import Any, cast

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import current_request_id

log = structlog.get_logger(__name__)

# HTTP status -> contract error code. Statuses not listed fall back to a code derived from the
# HTTP reason phrase (e.g. 405 -> "method_not_allowed").
STATUS_CODES: dict[int, str] = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    501: "not_implemented",
    503: "upstream_unavailable",
}


def code_for_status(status: int) -> str:
    if status in STATUS_CODES:
        return STATUS_CODES[status]
    try:
        return HTTPStatus(status).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "error"


class APIError(Exception):
    """Raise from anywhere in the request path to return a contract error."""

    def __init__(
        self,
        status_code: int,
        message: str,
        code: str | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code or code_for_status(status_code)
        self.message = message
        self.details = details
        self.headers = headers


class NotImplementedYet(APIError):
    def __init__(self, what: str) -> None:
        super().__init__(501, f"{what} is not implemented yet")


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": current_request_id(),
        }
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=error_body(code, message, details), headers=headers
    )


def _format_loc(loc: Sequence[Any]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or "request"


def _validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    return [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]


async def _api_error_handler(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(APIError, exc)
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    details = _validation_details(exc)
    first = details[0] if details else None
    message = f"{_format_loc(first['loc'])}: {first['msg']}" if first else "Invalid request"
    return error_response(422, "validation_error", message, details)


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    return error_response(
        exc.status_code,
        code_for_status(exc.status_code),
        message,
        headers=dict(exc.headers) if exc.headers else None,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    # Unhandled exceptions are turned into a 500 by RequestContextMiddleware, which also keeps
    # the X-Request-Id header on that response.
