"""Admin auth, rate limits, body size limit and /metrics (no database needed)."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_background, get_query_log_writer, get_search_service
from app.cli import main as cli_main
from app.core.ratelimit import RateLimiter, client_key
from app.core.security import (
    InvalidToken,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.main import create_app
from tests.conftest import make_settings
from tests.unit.test_search_endpoint import wire
from tests.unit.test_search_service import make_service

QUERY_ID = "5f0c2a9e-3b1d-4c8e-9a47-2d6f8e1b0c3a"
SECRET = "unit-test-secret-with-enough-length"

ADMIN_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/v1/admin/stats", None),
    ("GET", "/api/v1/admin/queries?page=2&lang=kk&zero_results=true", None),
    ("GET", "/api/v1/admin/queries/export", None),
    ("GET", f"/api/v1/admin/queries/{QUERY_ID}", None),
    ("GET", "/api/v1/admin/system", None),
    ("POST", "/api/v1/admin/reindex", {"source": "sample"}),
    ("GET", f"/api/v1/admin/jobs/{QUERY_ID}", None),
]


# --- passwords and tokens ---------------------------------------------------------------------


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery")
    assert hashed.startswith("$2")
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_token_roundtrip_expiry_and_tampering() -> None:
    token = create_token("admin", SECRET, ttl_s=60)
    assert decode_token(token, SECRET)["sub"] == "admin"
    with pytest.raises(InvalidToken):
        decode_token(token, "another-secret-of-sufficient-length")
    with pytest.raises(InvalidToken):
        decode_token(create_token("admin", SECRET, ttl_s=60, now=1_000_000), SECRET)  # expired
    with pytest.raises(InvalidToken):
        decode_token(token[:-2] + "xx", SECRET)


def test_cli_hash_password(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["hash-password", "--password", "long-enough-password"]) == 0
    assert verify_password("long-enough-password", capsys.readouterr().out.strip())
    assert cli_main(["hash-password", "--password", "short"]) == 1


# --- admin routes need a valid token ----------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ROUTES)
def test_admin_routes_require_a_token(
    client: TestClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("kind", ["garbage", "expired", "wrong_secret", "wrong_scheme"])
def test_admin_rejects_bad_tokens(kind: str) -> None:
    settings = make_settings(jwt_secret=SECRET)
    token = {
        "garbage": "not.a.jwt",
        "expired": create_token("admin", SECRET, ttl_s=60, now=1_000_000),
        "wrong_secret": create_token("admin", "another-secret-of-sufficient-length", 60),
        "wrong_scheme": create_token("admin", SECRET, 60),
    }[kind]
    scheme = "Basic" if kind == "wrong_scheme" else "Bearer"
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/admin/stats", headers={"Authorization": f"{scheme} {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


# --- rate limits ------------------------------------------------------------------------------


def test_rate_limiter_window() -> None:
    now = [0.0]
    limiter = RateLimiter(clock=lambda: now[0])
    assert limiter.check("k", 2) is None
    assert limiter.check("k", 2) is None
    assert limiter.check("k", 2) == 60
    assert limiter.check("other", 2) is None  # keys are independent
    now[0] = 45.5
    assert limiter.check("k", 2) == 15  # ceil(60 - 45.5)
    now[0] = 60.0
    assert limiter.check("k", 2) is None  # the first hit left the window
    assert limiter.check("unlimited", 0) is None


def test_client_key_does_not_contain_the_ip() -> None:
    key = client_key("203.0.113.7", "session-1")
    assert "203.0.113.7" not in key
    assert key != client_key("203.0.113.8", "session-1")
    assert key != client_key("203.0.113.7", "session-2")


def limited_app(**overrides: Any) -> FastAPI:
    app = create_app(make_settings(rate_limit_search=2, **overrides))
    service, _, _ = make_service()
    wire(app, service)
    return app


def test_search_is_rate_limited_per_session_with_retry_after() -> None:
    with TestClient(limited_app()) as client:
        body = {"query": "зарплата"}
        session = {"X-Session-Id": "aaaaaaaa-0000-4000-8000-000000000001"}
        assert client.post("/api/v1/search", json=body, headers=session).status_code == 200
        assert client.post("/api/v1/search", json=body, headers=session).status_code == 200
        limited = client.post("/api/v1/search", json=body, headers=session)
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limited"
        assert 1 <= int(limited.headers["retry-after"]) <= 60
        # another session from the same address has its own budget
        other = {"X-Session-Id": "aaaaaaaa-0000-4000-8000-000000000002"}
        assert client.post("/api/v1/search", json=body, headers=other).status_code == 200


def test_valid_api_key_gets_higher_limits_and_an_invalid_one_does_not() -> None:
    app = limited_app(api_keys=["integration-key"], api_key_limit_factor=3)
    with TestClient(app) as client:
        body = {"query": "зарплата"}
        good = {"X-API-Key": "integration-key"}
        statuses = [
            client.post("/api/v1/search", json=body, headers=good).status_code for _ in range(7)
        ]
        assert statuses == [200] * 6 + [429]
    with TestClient(limited_app(api_keys=["integration-key"])) as client:
        bad = {"X-API-Key": "guess", "X-Session-Id": "aaaaaaaa-0000-4000-8000-000000000003"}
        statuses = [
            client.post("/api/v1/search", json=body, headers=bad).status_code for _ in range(3)
        ]
        assert statuses == [200, 200, 429]


# --- body size and metrics --------------------------------------------------------------------


def test_oversized_body_is_rejected_before_parsing() -> None:
    with TestClient(create_app(make_settings(max_body_bytes=1000))) as client:
        response = client.post("/api/v1/search", json={"query": "я" * 600})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "content_too_large"
    assert response.headers["x-request-id"]


def test_metrics_endpoint_reports_search_and_http_metrics(app: FastAPI) -> None:
    service, _, _ = make_service()
    wire(app, service)
    assert get_search_service in app.dependency_overrides
    assert get_query_log_writer in app.dependency_overrides
    assert get_background in app.dependency_overrides
    with TestClient(app) as client:
        assert client.post("/api/v1/search", json={"query": "зарплата"}).status_code == 200
        client.get(f"/api/v1/admin/jobs/{QUERY_ID}")
        text = client.get("/metrics").text
    assert 'search_requests_total{lang="ru",mode="hybrid",status="ok"}' in text
    assert 'search_stage_latency_seconds_count{stage="total"}' in text
    assert 'http_requests_total{method="POST",path="/api/v1/search",status="200"}' in text
    # the route template is the label, never the id from the path
    assert 'path="/api/v1/admin/jobs/{job_id}"' in text
    assert QUERY_ID not in text
    # /metrics is internal: it is not part of the public API schema
    assert "/metrics" not in client.get("/api/v1/openapi.json").json()["paths"]
