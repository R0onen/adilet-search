"""OpenAPI `responses` helpers: every documented error uses the contract error shape."""

from typing import Any

from app.schemas.common import ErrorResponse

_DESCRIPTIONS = {
    401: "Missing or invalid admin token",
    404: "Not found",
    409: "Conflict",
    422: "Validation error",
    429: "Rate limited (see the `Retry-After` header)",
    500: "Internal error",
    501: "Not implemented yet (stub)",
    503: "A required upstream component is unavailable",
}


def errors(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return {
        status: {"model": ErrorResponse, "description": _DESCRIPTIONS[status]}
        for status in (*statuses, 500)
    }
