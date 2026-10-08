"""POST /search wiring: response, request context, query log written for success and failure."""

import asyncio
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_background, get_query_log_writer, get_search_service
from app.core.errors import APIError
from app.schemas.search import SearchRequest
from app.services.search import SearchContext, SearchError, SearchOutcome
from tests.unit.test_search_service import make_service


class RecordingLog:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def write(self, values: dict[str, Any]) -> None:
        self.rows.append(values)


class InlineBackground:
    """Runs spawned coroutines immediately, so the test can see their effect."""

    def __init__(self) -> None:
        self.coros: list[Any] = []

    def spawn(self, coro: Any) -> None:
        self.coros.append(coro)

    async def run_all(self) -> None:
        for coro in self.coros:
            await coro


class FailingSearch:
    async def search(self, request: SearchRequest, ctx: SearchContext) -> SearchOutcome:
        raise SearchError(APIError(503, "down", code="upstream_unavailable"), {"query": "q"})


def wire(app: FastAPI, service: Any) -> tuple[RecordingLog, InlineBackground]:
    log, background = RecordingLog(), InlineBackground()
    app.dependency_overrides[get_search_service] = lambda: service
    app.dependency_overrides[get_query_log_writer] = lambda: log
    app.dependency_overrides[get_background] = lambda: background
    return log, background


def test_search_returns_contract_shape_and_logs(app: FastAPI, client: TestClient) -> None:
    service, _, _ = make_service()
    log, background = wire(app, service)
    response = client.post(
        "/api/v1/search",
        json={"query": "Ответственность работодателя за задержку зарплаты", "top_k": 3},
        headers={"X-Session-Id": "6f1a2b3c-0000-4000-8000-00000000abcd"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "query_id",
        "query",
        "lang",
        "mode",
        "results",
        "total_candidates",
        "degraded",
        "timing_ms",
        "pipeline_version",
    }
    assert len(body["results"]) == 3
    assert body["results"][0]["article"]["article_id"].startswith("T0000000001:ru:")

    asyncio.run(background.run_all())
    assert len(log.rows) == 1
    row = log.rows[0]
    assert str(row["query_id"]) == body["query_id"]
    assert row["client"] == "web"
    assert row["session_hash"] is not None
    assert "6f1a2b3c" not in row["session_hash"]


def test_failed_search_is_logged_and_returns_503(app: FastAPI, client: TestClient) -> None:
    log, background = wire(app, FailingSearch())
    response = client.post("/api/v1/search", json={"query": "зарплата"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"
    asyncio.run(background.run_all())
    assert log.rows == [{"query": "q"}]


def test_api_key_client_is_tagged(app: FastAPI, client: TestClient) -> None:
    service, _, _ = make_service()
    log, background = wire(app, service)
    client.post("/api/v1/search", json={"query": "зарплата"}, headers={"X-API-Key": "k"})
    asyncio.run(background.run_all())
    assert log.rows[0]["client"] == "api-key"
    assert log.rows[0]["session_hash"] is None
