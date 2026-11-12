"""Per-application HTTP metrics, including completed streaming responses.

Labels use route templates, never user input or individual article identifiers.
"""

import time

from prometheus_client import CollectorRegistry, Counter, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class HttpMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "adilet_http_requests_total",
            "Completed HTTP requests",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "adilet_http_request_duration_seconds",
            "HTTP duration including streaming",
            ["method", "route"],
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 30, 90),
            registry=self.registry,
        )


class MetricsMiddleware:
    def __init__(self, app: ASGIApp, metrics: HttpMetrics) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def observed_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, observed_send)
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            method = (
                scope["method"]
                if scope["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                else "OTHER"
            )
            self.metrics.requests.labels(method, route, str(status)).inc()
            self.metrics.duration.labels(method, route).observe(time.perf_counter() - started)
