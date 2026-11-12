"""Prometheus metrics. Scraped at `/metrics` (root path; not exposed through the reverse proxy)."""

import time

from prometheus_client import CollectorRegistry, Counter, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send

STAGE_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
ANSWER_BUCKETS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0, 60.0, 120.0)

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
HTTP_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "path"],
    buckets=STAGE_BUCKETS,
)  # fmt: skip

SEARCH_REQUESTS = Counter("search_requests_total", "Search requests", ["mode", "lang", "status"])
SEARCH_STAGE = Histogram(
    "search_stage_latency_seconds", "Search latency per stage", ["stage"], buckets=STAGE_BUCKETS
)
SEARCH_ZERO = Counter("search_zero_results_total", "Searches that returned nothing")
DEGRADED = Counter("degraded_responses_total", "Degraded responses", ["component"])
ANSWER_TTFT = Histogram(
    "answer_ttft_seconds", "Time to the first answer token", buckets=ANSWER_BUCKETS
)
ANSWER_DURATION = Histogram(
    "answer_duration_seconds", "Answer generation time", buckets=ANSWER_BUCKETS
)
ANSWERS = Counter("answers_total", "Answer streams by outcome", ["status"])
CITATIONS_INVALID = Counter("answer_citations_invalid_total", "Invalid citations removed")
FEEDBACK = Counter("feedback_total", "Feedback events", ["target", "rating"])
ML_ERRORS = Counter("ml_client_errors_total", "ML service call failures", ["endpoint", "kind"])
CACHE_HITS = Counter("cache_hits_total", "Cache hits", ["cache"])
CACHE_MISSES = Counter("cache_misses_total", "Cache misses", ["cache"])
RATE_LIMITED = Counter("rate_limited_total", "Requests rejected by the rate limiter", ["scope"])


def observe_search(mode: str, lang: str, timing_ms: dict[str, int], degraded: list[str],
                   zero_results: bool) -> None:  # fmt: skip
    SEARCH_REQUESTS.labels(mode, lang, "ok").inc()
    for stage, value in timing_ms.items():
        SEARCH_STAGE.labels(stage).observe(value / 1000)
    for component in degraded:
        DEGRADED.labels(component).inc()
    if zero_results:
        SEARCH_ZERO.inc()


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
