"""Error shape (contracts/api.md §1), request ids, CORS, and the 501 stubs."""

import re
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
QUERY_ID = "5f0c2a9e-3b1d-4c8e-9a47-2d6f8e1b0c3a"
ARTICLE_ID = "K1500000414:ru:a113"


def assert_error(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"]
    assert error["request_id"] == response.headers["X-Request-Id"]
    return error


def test_unknown_route_is_404(client: TestClient) -> None:
    assert_error(client.get("/api/v1/nope"), 404, "not_found")


def test_wrong_method_is_405(client: TestClient) -> None:
    assert_error(client.get("/api/v1/search"), 405, "method_not_allowed")


@pytest.mark.parametrize(
    "body",
    [
        {"query": ""},
        {"query": "   \n\t "},
        {"query": "я" * 501},
        {"query": "зарплата", "top_k": 0},
        {"query": "зарплата", "top_k": 51},
        {"query": "зарплата", "lang": "kz"},
        {"query": "зарплата", "mode": "fuzzy"},
        {"query": "зарплата", "filters": {"doc_types": ["novel"]}},
        {"query": "зарплата", "filters": {"date_from": "2020-01-02", "date_to": "2020-01-01"}},
        {},
    ],
)
def test_search_validation_is_422(client: TestClient, body: dict[str, Any]) -> None:
    error = assert_error(client.post("/api/v1/search", json=body), 422, "validation_error")
    assert isinstance(error["details"], list)
    assert {"loc", "msg", "type"} <= set(error["details"][0])


def test_query_message_matches_contract(client: TestClient) -> None:
    error = assert_error(
        client.post("/api/v1/search", json={"query": " "}), 422, "validation_error"
    )
    assert "Query must be 1–500 characters" in error["message"]


def test_malformed_json_is_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/search", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert_error(response, 422, "validation_error")


def test_feedback_requires_article_for_result(client: TestClient) -> None:
    body = {"query_id": QUERY_ID, "target": "result", "rating": 1}
    assert_error(client.post("/api/v1/feedback", json=body), 422, "validation_error")


@pytest.mark.parametrize("rating", [0, 2, -2])
def test_feedback_rating_is_plus_or_minus_one(client: TestClient, rating: int) -> None:
    body = {"query_id": QUERY_ID, "target": "answer", "rating": rating}
    assert_error(client.post("/api/v1/feedback", json=body), 422, "validation_error")


def test_answer_context_top_k_range(client: TestClient) -> None:
    body = {"query": "зарплата", "context_top_k": 9}
    assert_error(client.post("/api/v1/answer", json=body), 422, "validation_error")


STUBS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("POST", "/api/v1/answer", {"query": "Еңбек шартын бұзу негіздері"}),
    ("POST", "/api/v1/feedback", {"query_id": QUERY_ID, "target": "answer", "rating": -1}),
    ("POST", "/api/v1/admin/login", {"username": "admin", "password": "x"}),
    ("GET", "/api/v1/admin/stats", None),
    ("GET", "/api/v1/admin/queries?page=2&lang=kk&zero_results=true", None),
    ("GET", "/api/v1/admin/queries/export", None),
    ("GET", f"/api/v1/admin/queries/{QUERY_ID}", None),
    ("GET", "/api/v1/admin/system", None),
    ("POST", "/api/v1/admin/reindex", {"source": "sample"}),
    ("GET", f"/api/v1/admin/jobs/{QUERY_ID}", None),
]


@pytest.mark.parametrize(("method", "path", "body"), STUBS)
def test_stubs_return_501(
    client: TestClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = client.request(method, path, json=body)
    assert_error(response, 501, "not_implemented")


def test_unhandled_exception_is_500_with_request_id(app: FastAPI) -> None:
    @app.get("/api/v1/_boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        error = assert_error(client.get("/api/v1/_boom"), 500, "internal_error")
    assert "boom" not in error["message"]  # internals are not leaked


def test_request_id_is_generated(client: TestClient) -> None:
    response = client.get("/api/v1/version")
    assert REQUEST_ID.match(response.headers["X-Request-Id"])


def test_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/api/v1/version", headers={"X-Request-Id": "frontend-req-0001"})
    assert response.headers["X-Request-Id"] == "frontend-req-0001"
    error = client.get("/api/v1/nope", headers={"X-Request-Id": "frontend-req-0002"}).json()
    assert error["error"]["request_id"] == "frontend-req-0002"


@pytest.mark.parametrize("bad", ["short", "has spaces in it", "x" * 129, "inject line"])
def test_unsafe_request_id_is_replaced(client: TestClient, bad: str) -> None:
    response = client.get("/api/v1/version", headers={"X-Request-Id": bad.encode("utf-8")})  # type: ignore[dict-item]
    assert REQUEST_ID.match(response.headers["X-Request-Id"])


def test_cors_allows_dev_frontend(client: TestClient) -> None:
    response = client.options(
        "/api/v1/search",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-session-id",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "X-Request-Id" in response.headers


def test_cors_rejects_other_origins(client: TestClient) -> None:
    response = client.get("/api/v1/version", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_exposes_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/version", headers={"Origin": "http://localhost:5173"})
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()
