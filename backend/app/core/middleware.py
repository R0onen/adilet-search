"""Request context middleware: request id, access log and the last-resort 500 handler.

Pure ASGI (not BaseHTTPMiddleware) so that it does not buffer streaming (SSE) responses.
"""

import json
import re
import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import metrics
from app.core.context import request_id_var
from app.core.errors import error_body

log = structlog.get_logger("app.request")

REQUEST_ID_HEADER = "X-Request-Id"
# Accept client ids only if they are short and safe to put in logs and headers.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"x-request-id":
            candidate = value.decode("latin-1")
            return candidate if _VALID_REQUEST_ID.match(candidate) else None
    return None


def _route_template(scope: Scope) -> str:
    """The matched path with parameter values replaced by their names; "unmatched" for a 404."""
    if scope.get("route") is None:
        return "unmatched"
    path = str(scope.get("path", ""))
    for name, value in (scope.get("path_params") or {}).items():
        path = path.replace(str(value), "{" + name + "}")
    return path


def _content_length(scope: Scope) -> int:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return 0
    return 0


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int = 0) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        if self.max_body_bytes and _content_length(scope) > self.max_body_bytes:
            body = json.dumps(
                error_body(
                    "content_too_large", f"The request body exceeds {self.max_body_bytes} bytes"
                ),
                ensure_ascii=False,
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        (REQUEST_ID_HEADER.lower().encode(), request_id.encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            metrics.HTTP_REQUESTS.labels(str(scope.get("method")), "rejected", "413").inc()
            structlog.contextvars.unbind_contextvars("request_id")
            request_id_var.reset(token)
            return

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log.exception("unhandled_exception", path=scope.get("path"))
            if response_started:
                raise
            status_code = 500
            body = json.dumps(
                error_body("internal_error", "Internal server error"), ensure_ascii=False
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        (REQUEST_ID_HEADER.lower().encode(), request_id.encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
        finally:
            duration_s = time.perf_counter() - started
            log.info(
                "request",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status_code,
                duration_ms=round(duration_s * 1000, 1),
            )
            # The route template, not the raw path: ids in paths must not become label values.
            route = _route_template(scope)
            method = str(scope.get("method"))
            metrics.HTTP_REQUESTS.labels(method, route, str(status_code)).inc()
            metrics.HTTP_DURATION.labels(method, route).observe(duration_s)
            structlog.contextvars.unbind_contextvars("request_id")
            request_id_var.reset(token)
