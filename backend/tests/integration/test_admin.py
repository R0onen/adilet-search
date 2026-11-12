"""Admin API and degraded-mode drills on real postgres, qdrant and fake-ml.

Uses its own database (`<test db>_admin`) and alias (`test_admin_chunks`). The query log is
seeded with fixed rows, so the statistics are checked against exact numbers.
"""

import asyncio
import csv
import io
import json
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.state import Resources
from dev.sample_corpus import write
from indexer.pipeline import Indexer, IndexOptions
from tests.conftest import REPO_ROOT, make_settings
from tests.integration.conftest import (
    TEST_DATABASE_URL,
    TEST_ML_SERVICE_URL,
    TEST_QDRANT_URL,
    _ensure_database,
    plain_dsn,
)

pytestmark = pytest.mark.integration

ALIAS = "test_admin_chunks"
ADMIN_DB_URL = TEST_DATABASE_URL + "_admin"
PASSWORD = "integration-test-password"
PASSWORD_HASH = hash_password(PASSWORD)
QUERY_RU = "Ответственность работодателя за задержку зарплаты"
DEAD_URL = "http://127.0.0.1:9"  # nothing listens on the discard port

# (day, hour, query, lang, mode, result_count, search_ms, degraded, session, has_answer)
SEED: list[tuple[int, int, str, str, str, int, int, list[str], str, bool]] = [
    (1, 9, "Задержка зарплаты", "ru", "hybrid", 10, 100, [], "s1", True),
    (1, 10, "задержка   зарплаты", "ru", "hybrid", 10, 200, [], "s1", False),
    (1, 11, "отпуск", "ru", "keyword", 5, 300, [], "s2", False),
    (2, 9, "еңбек демалысы", "kk", "hybrid", 8, 400, ["rerank"], "s2", False),
    (2, 10, "нет такого", "ru", "hybrid", 0, 500, [], "s3", False),
    (4, 9, "нет такого", "ru", "semantic", 0, 600, ["semantic"], "s3", False),
]
SEED_IDS = [uuid.UUID(int=number) for number in range(1, len(SEED) + 1)]


def settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": ADMIN_DB_URL,
        "qdrant_url": TEST_QDRANT_URL,
        "qdrant_alias": ALIAS,
        "ml_service_url": TEST_ML_SERVICE_URL,
        "manifest_source": "service",
        "index_state_ttl_s": 0,
        "admin_username": "admin",
        "admin_password_hash": PASSWORD_HASH,
        "jwt_secret": "integration-test-jwt-secret-0123456789",
        "rate_limit_login": 0,
        "cache_ttl_s": 0,
    }
    values.update(overrides)
    return make_settings(**values)


def sql(query: str, *args: Any) -> list[asyncpg.Record]:
    async def go() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(plain_dsn(ADMIN_DB_URL))
        try:
            return await conn.fetch(query, *args)
        finally:
            await conn.close()

    return asyncio.run(go())


def seed_logs() -> None:
    for query_id, row in zip(SEED_IDS, SEED, strict=True):
        day, hour, query, lang, mode, count, ms, degraded, session, has_answer = row
        sql(
            "INSERT INTO query_logs (query_id, created_at, session_hash, endpoint, query, "
            "query_norm, lang, mode, top_k, result_count, zero_results, top_article_id, results, "
            "timing_ms, search_ms, degraded, has_answer, pipeline_version, filters) "
            "VALUES ($1, $2, $3, 'search', $4, $5, $6, $7, 10, $8, $9, $10, $11::jsonb, "
            "$12::jsonb, $13, $14, $15, '0.0.0-fake', '{}'::jsonb)",
            query_id,
            datetime(2026, 3, day, hour, tzinfo=UTC),
            session,
            query,
            " ".join(query.lower().split()),
            lang,
            mode,
            count,
            count == 0,
            "T0000000001:ru:a113" if count else None,
            json.dumps(
                [
                    {
                        "rank": 1,
                        "article_id": "T0000000001:ru:a113",
                        "score": 0.9,
                        "title": "Сроки выплаты",
                        "doc_short_title": "Тестовый ТК",
                    }
                ]
                if count
                else []
            ),
            json.dumps({"embed": 10, "total": ms}),
            ms,
            degraded,
            has_answer,
        )
    sql(
        "INSERT INTO answers (answer_id, query_id, created_at, status, text, citations, grounded, "
        "search_ms, ttft_ms, total_ms) VALUES ($1, $2, $3, 'completed', 'Ответ [1].', '{1}', true, "
        "100, 1500, 4000)",
        uuid.UUID(int=101),
        SEED_IDS[0],
        datetime(2026, 3, 1, 9, tzinfo=UTC),
    )
    for query_id, target, article, rating in (
        (SEED_IDS[0], "answer", None, 1),
        (SEED_IDS[0], "result", "T0000000001:ru:a113", 1),
        (SEED_IDS[2], "result", "T0000000001:ru:a113", -1),
    ):
        sql(
            "INSERT INTO feedback (query_id, session_hash, target, article_id, rating, created_at) "
            "VALUES ($1, 's1', $2, $3, $4, $5)",
            query_id,
            target,
            article,
            rating,
            datetime(2026, 3, 1, 12, tzinfo=UTC),
        )


@pytest.fixture(scope="module")
def data_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("data")
    write(root / "sample")
    return root


@pytest.fixture(scope="module")
def environment(data_root: Path) -> None:
    """Fresh schema, seeded logs, an empty alias and one index of the synthetic corpus."""
    asyncio.run(_ensure_database(ADMIN_DB_URL))
    config = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", ADMIN_DB_URL)
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    async def build() -> None:
        from qdrant_client import models as qm

        resources = Resources.create(settings())
        try:
            client = resources.qdrant.client
            aliases = await client.get_aliases()
            if any(a.alias_name == ALIAS for a in aliases.aliases):
                await client.update_collection_aliases(
                    change_aliases_operations=[
                        qm.DeleteAliasOperation(delete_alias=qm.DeleteAlias(alias_name=ALIAS))
                    ]
                )
            for collection in (await client.get_collections()).collections:
                if collection.name.startswith(f"{ALIAS}__"):
                    await client.delete_collection(collection.name)
            manifest = await resources.manifest.get()
            assert manifest is not None, "fake-ml /version is not reachable"
            indexer = Indexer(resources.sessionmaker, resources.qdrant, resources.ml, manifest)
            await indexer.run(IndexOptions(data_dir=data_root / "sample"))
        finally:
            await resources.aclose()

    asyncio.run(build())
    seed_logs()


@pytest.fixture(scope="module")
def client(environment: None, data_root: Path) -> Iterator[TestClient]:
    with TestClient(create_app(settings(data_dir=str(data_root)))) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/admin/login", json={"username": "admin", "password": PASSWORD})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 8 * 3600
    return {"Authorization": f"Bearer {body['access_token']}"}


MARCH = {"date_from": "2026-03-01", "date_to": "2026-03-04"}

# --- login ------------------------------------------------------------------------------------


def test_login_seeds_the_admin_and_records_the_login(auth: dict[str, str]) -> None:
    rows = sql("SELECT username, is_active, last_login_at FROM admin_users")
    assert [(r["username"], r["is_active"]) for r in rows] == [("admin", True)]
    assert rows[0]["last_login_at"] is not None


@pytest.mark.parametrize(
    "credentials",
    [{"username": "admin", "password": "wrong"}, {"username": "nobody", "password": PASSWORD}],
)
def test_wrong_credentials_are_401(client: TestClient, credentials: dict[str, str]) -> None:
    response = client.post("/api/v1/admin/login", json=credentials)
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Wrong username or password"


def test_login_is_rate_limited(environment: None) -> None:
    with TestClient(create_app(settings(rate_limit_login=2))) as limited:
        body = {"username": "admin", "password": "wrong"}
        statuses = [limited.post("/api/v1/admin/login", json=body).status_code for _ in range(3)]
    assert statuses == [401, 401, 429]


# --- statistics -------------------------------------------------------------------------------


def test_stats_exact_numbers(client: TestClient, auth: dict[str, str]) -> None:
    response = client.get("/api/v1/admin/stats", params=MARCH, headers=auth)
    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats["date_from"] == "2026-03-01"
    assert stats["date_to"] == "2026-03-04"
    assert stats["totals"] == {
        "queries": 6,
        "unique_sessions": 3,
        "answers": 1,
        "feedback_positive": 2,
        "feedback_negative": 1,
        "zero_result_queries": 2,
    }
    assert stats["rates"] == {
        "zero_result_rate": 0.3333,
        "satisfaction_rate": 0.6667,
        "degraded_rate": 0.3333,
    }
    # percentile_cont over 100..600: p50 = 350, p95 = 575; one answer with ttft 1500
    assert stats["latency_ms"] == {
        "search_p50": 350,
        "search_p95": 575,
        "answer_ttft_p50": 1500,
        "answer_ttft_p95": 1500,
    }
    assert stats["by_day"] == [
        {"date": "2026-03-01", "queries": 3, "search_p95_ms": 290, "zero_result_rate": 0.0},
        {"date": "2026-03-02", "queries": 2, "search_p95_ms": 495, "zero_result_rate": 0.5},
        # a day without queries is present, with zeros
        {"date": "2026-03-03", "queries": 0, "search_p95_ms": None, "zero_result_rate": None},
        {"date": "2026-03-04", "queries": 1, "search_p95_ms": 600, "zero_result_rate": 1.0},
    ]
    assert stats["by_lang"] == [{"lang": "ru", "queries": 5}, {"lang": "kk", "queries": 1}]
    assert stats["by_mode"] == [
        {"mode": "hybrid", "queries": 4},
        {"mode": "keyword", "queries": 1},
        {"mode": "semantic", "queries": 1},
    ]
    # grouped by the normalised query: case and repeated spaces do not split a group
    assert stats["top_queries"][:2] == [
        {"query": "задержка зарплаты", "count": 2},
        {"query": "нет такого", "count": 2},
    ]
    assert stats["top_zero_result_queries"] == [{"query": "нет такого", "count": 2}]


def test_stats_range_is_inclusive_and_validated(client: TestClient, auth: dict[str, str]) -> None:
    one_day = {"date_from": "2026-03-02", "date_to": "2026-03-02"}
    stats = client.get("/api/v1/admin/stats", params=one_day, headers=auth).json()
    assert stats["totals"]["queries"] == 2
    assert len(stats["by_day"]) == 1

    default = client.get("/api/v1/admin/stats", headers=auth).json()
    assert len(default["by_day"]) == 7  # the last 7 days

    backwards = {"date_from": "2026-03-05", "date_to": "2026-03-01"}
    assert client.get("/api/v1/admin/stats", params=backwards, headers=auth).status_code == 422


# --- query log --------------------------------------------------------------------------------


def listed(client: TestClient, auth: dict[str, str], **params: Any) -> dict[str, Any]:
    response = client.get("/api/v1/admin/queries", params={**MARCH, **params}, headers=auth)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_query_list_is_newest_first_and_paginated(client: TestClient, auth: dict[str, str]) -> None:
    page = listed(client, auth, page=1, page_size=4)
    assert (page["total"], page["page"], page["page_size"]) == (6, 1, 4)
    assert [item["query_id"] for item in page["items"]] == [str(i) for i in reversed(SEED_IDS[2:])]
    rest = listed(client, auth, page=2, page_size=4)
    assert [item["query_id"] for item in rest["items"]] == [str(SEED_IDS[1]), str(SEED_IDS[0])]
    first = rest["items"][1]
    assert first["feedback"] == {"positive": 2, "negative": 0}
    assert first["has_answer"] is True
    assert first["top_article_id"] == "T0000000001:ru:a113"
    assert first["search_ms"] == 100


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"lang": "kk"}, [4]),
        ({"mode": "keyword"}, [3]),
        ({"zero_results": "true"}, [6, 5]),
        ({"zero_results": "false", "lang": "ru"}, [3, 2, 1]),
        ({"degraded": "true"}, [6, 4]),
        ({"feedback": "positive"}, [1]),
        ({"feedback": "negative"}, [3]),
        ({"q": "ЗАРПЛАТЫ"}, [2, 1]),
        ({"q": "100%_"}, []),  # LIKE wildcards are plain characters here
        ({"date_from": "2026-03-02", "date_to": "2026-03-02"}, [5, 4]),
    ],
)
def test_query_list_filters(
    client: TestClient, auth: dict[str, str], params: dict[str, str], expected: list[int]
) -> None:
    page = listed(client, auth, **params)
    assert [uuid.UUID(item["query_id"]).int for item in page["items"]] == expected
    assert page["total"] == len(expected)


def test_query_detail(client: TestClient, auth: dict[str, str]) -> None:
    response = client.get(f"/api/v1/admin/queries/{SEED_IDS[0]}", headers=auth)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["query"] == "Задержка зарплаты"
    assert detail["top_k"] == 10
    assert detail["filters"]["in_force_only"] is True
    assert detail["results"] == [
        {
            "rank": 1,
            "article_id": "T0000000001:ru:a113",
            "title": "Сроки выплаты",
            "doc_short_title": "Тестовый ТК",
            "score": 0.9,
        }
    ]
    assert detail["timing_ms"] == {"embed": 10, "total": 100}
    assert detail["answer"]["text"] == "Ответ [1]."
    assert detail["answer"]["citations"] == [1]
    assert detail["answer"]["timing_ms"] == {"search": 100, "ttft": 1500, "total": 4000}
    assert [(f["target"], f["rating"]) for f in detail["feedback_items"]] == [
        ("answer", 1),
        ("result", 1),
    ]
    assert detail["session_hash"] == "s1"
    assert detail["pipeline_version"] == "0.0.0-fake"

    no_answer = client.get(f"/api/v1/admin/queries/{SEED_IDS[4]}", headers=auth).json()
    assert no_answer["answer"] is None
    assert no_answer["results"] == []

    missing = client.get(f"/api/v1/admin/queries/{uuid.uuid4()}", headers=auth)
    assert missing.status_code == 404


def test_csv_export(client: TestClient, auth: dict[str, str]) -> None:
    params = {**MARCH, "lang": "ru"}
    response = client.get("/api/v1/admin/queries/export", params=params, headers=auth)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM, for Excel
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == [
        "query_id", "created_at", "query", "lang", "mode", "result_count", "top_article_id",
        "search_ms", "has_answer", "feedback_positive", "feedback_negative", "degraded",
    ]  # fmt: skip
    assert len(rows) == 1 + 5  # the Kazakh query is filtered out
    assert rows[1] == [
        str(SEED_IDS[5]), "2026-03-04T09:00:00Z", "нет такого", "ru", "semantic", "0", "", "600",
        "false", "0", "0", "semantic",
    ]  # fmt: skip
    assert rows[5][2] == "Задержка зарплаты"
    assert rows[5][8:11] == ["true", "2", "0"]


# --- system and reindex -----------------------------------------------------------------------


def test_system(client: TestClient, auth: dict[str, str]) -> None:
    response = client.get("/api/v1/admin/system", headers=auth)
    assert response.status_code == 200, response.text
    system = response.json()
    assert system["components"]["database"] == "ok"
    assert system["components"]["qdrant"] == "ok"
    assert system["components"]["ml_service"] == "ok"
    assert system["pipeline"]["pipeline_version"] == "0.0.0-fake"
    assert system["pipeline"]["embedder"]
    index = system["index"]
    assert index["alias"] == ALIAS
    assert index["collection"].startswith(f"{ALIAS}__")
    assert index["points"] > 0
    assert index["articles"] > 0
    assert index["compatible"] is True
    assert index["last_job"]["status"] == "succeeded"
    assert system["uptime_s"] >= 0


def test_reindex_job_lifecycle_and_conflict(client: TestClient, auth: dict[str, str]) -> None:
    before = client.get("/api/v1/admin/system", headers=auth).json()["index"]["collection"]

    blocker = uuid.uuid4()
    sql("INSERT INTO index_jobs (job_id, status) VALUES ($1, 'running')", blocker)
    try:
        conflict = client.post("/api/v1/admin/reindex", json={"source": "sample"}, headers=auth)
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "conflict"
    finally:
        sql("DELETE FROM index_jobs WHERE job_id = $1", blocker)

    missing = client.post("/api/v1/admin/reindex", json={"source": "processed"}, headers=auth)
    assert missing.status_code == 422  # this data root has no `processed` corpus

    started = client.post("/api/v1/admin/reindex", json={"source": "sample"}, headers=auth)
    assert started.status_code == 202, started.text
    job_id = started.json()["job_id"]
    job: dict[str, Any] = {}
    for _ in range(100):
        job = client.get(f"/api/v1/admin/jobs/{job_id}", headers=auth).json()
        if job["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)
    assert job["status"] == "succeeded", job
    assert job["progress"] == 1.0
    assert job["finished_at"] is not None

    after = client.get("/api/v1/admin/system", headers=auth).json()["index"]
    assert after["collection"] != before  # built next to the old one, then the alias moved
    assert after["last_job"]["job_id"] == job_id
    assert client.post("/api/v1/search", json={"query": QUERY_RU}).json()["results"]

    assert client.get(f"/api/v1/admin/jobs/{uuid.uuid4()}", headers=auth).status_code == 404


def test_interrupted_api_jobs_are_failed_at_startup(environment: None) -> None:
    api_job, cli_job = uuid.uuid4(), uuid.uuid4()
    sql(
        "INSERT INTO index_jobs (job_id, status, params) VALUES ($1, 'running', $2::jsonb)",
        api_job,
        json.dumps({"origin": "api"}),
    )
    try:
        with TestClient(create_app(settings())):
            pass
        rows = sql("SELECT status, error FROM index_jobs WHERE job_id = $1", api_job)
        assert rows[0]["status"] == "failed"
        assert rows[0]["error"].startswith("interrupted")

        # A job started with the CLI may really be running in another process: left alone.
        sql("INSERT INTO index_jobs (job_id, status) VALUES ($1, 'running')", cli_job)
        with TestClient(create_app(settings())):
            pass
        assert sql("SELECT status FROM index_jobs WHERE job_id = $1", cli_job)[0]["status"] == (
            "running"
        )
    finally:
        sql("DELETE FROM index_jobs WHERE job_id = ANY($1::uuid[])", [api_job, cli_job])


# --- degraded-mode drills ---------------------------------------------------------------------


def degraded_search(**overrides: Any) -> dict[str, Any]:
    with TestClient(create_app(settings(**overrides))) as degraded:
        response = degraded.post("/api/v1/search", json={"query": QUERY_RU, "top_k": 5})
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        health = degraded.get("/api/v1/health").json()
    body["_health"] = health
    return body


def test_ml_service_down_falls_back_to_full_text(environment: None) -> None:
    body = degraded_search(ml_service_url=DEAD_URL, manifest_source="file")
    assert body["degraded"] == ["semantic"]
    assert body["results"], "the full-text fallback found nothing"
    assert {r["score_type"] for r in body["results"]} == {"fts"}
    assert all(r["lang"] == "ru" for r in body["results"])
    assert any("заработн" in r["snippet"].lower() for r in body["results"])
    assert body["_health"]["components"]["ml_service"] == "down"
    assert body["_health"]["status"] == "degraded"


def test_qdrant_down_falls_back_to_full_text(environment: None) -> None:
    body = degraded_search(qdrant_url=DEAD_URL, qdrant_prefer_grpc=False, qdrant_timeout_s=1)
    assert body["degraded"] == ["semantic"]
    assert body["results"]
    assert body["results"][0]["score_type"] == "fts"


def test_full_text_fallback_respects_filters_and_language(environment: None) -> None:
    with TestClient(create_app(settings(ml_service_url=DEAD_URL, manifest_source="file"))) as api:
        kk = api.post("/api/v1/search", json={"query": "жалақы төлеу", "lang": "kk"}).json()
        assert kk["degraded"] == ["semantic"]
        assert all(r["lang"] == "kk" for r in kk["results"])

        filtered = api.post(
            "/api/v1/search",
            json={"query": QUERY_RU, "filters": {"doc_ids": ["T0000000002"]}},
        ).json()
        assert all(r["doc"]["doc_id"] == "T0000000002" for r in filtered["results"])

        nothing = api.post("/api/v1/search", json={"query": "zzzqqqxxx"}).json()
        assert nothing["results"] == []
        assert nothing["degraded"] == ["semantic"]


def test_degraded_search_is_logged_and_counted(environment: None) -> None:
    with TestClient(create_app(settings(ml_service_url=DEAD_URL, manifest_source="file"))) as api:
        body = api.post("/api/v1/search", json={"query": QUERY_RU}).json()
        metrics = api.get("/metrics").text
    assert 'degraded_responses_total{component="semantic"}' in metrics
    for _ in range(50):
        rows = sql(
            "SELECT degraded FROM query_logs WHERE query_id = $1", uuid.UUID(body["query_id"])
        )
        if rows:
            break
        time.sleep(0.1)
    assert rows[0]["degraded"] == ["semantic"]
