"""Indexer + search + documents/articles on real postgres, qdrant and fake-ml.

Uses its own database (`<test db>_search`) and alias (`test_legal_chunks`), so it never touches
dev data or the migration tests. The corpus is the synthetic one from dev/sample_corpus.py.
"""

import asyncio
import json
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.state import Resources
from dev.sample_corpus import build, write
from indexer.corpus import CorpusError
from indexer.pipeline import Indexer, IndexOptions, IndexResult, JobConflict
from tests.conftest import REPO_ROOT, make_settings
from tests.integration.conftest import (
    TEST_DATABASE_URL,
    TEST_ML_SERVICE_URL,
    TEST_QDRANT_URL,
    _ensure_database,
    plain_dsn,
)

pytestmark = pytest.mark.integration

ALIAS = "test_legal_chunks"
SEARCH_DB_URL = TEST_DATABASE_URL + "_search"
QUERY_RU = "Ответственность работодателя за задержку зарплаты"


def settings() -> Settings:
    return make_settings(
        database_url=SEARCH_DB_URL,
        qdrant_url=TEST_QDRANT_URL,
        qdrant_alias=ALIAS,
        ml_service_url=TEST_ML_SERVICE_URL,
        manifest_source="service",
        index_state_ttl_s=0,
    )


async def _drop_test_collections(resources: Resources) -> None:
    client = resources.qdrant.client
    aliases = await client.get_aliases()
    if any(a.alias_name == ALIAS for a in aliases.aliases):
        from qdrant_client import models as qm

        await client.update_collection_aliases(
            change_aliases_operations=[
                qm.DeleteAliasOperation(delete_alias=qm.DeleteAlias(alias_name=ALIAS))
            ]
        )
    for collection in (await client.get_collections()).collections:
        if collection.name.startswith(f"{ALIAS}__"):
            await client.delete_collection(collection.name)


async def run_indexer(data_dir: Path, **options: Any) -> IndexResult:
    resources = Resources.create(settings())
    try:
        manifest = await resources.manifest.get()
        assert manifest is not None, "fake-ml /version is not reachable"
        indexer = Indexer(resources.sessionmaker, resources.qdrant, resources.ml, manifest)
        return await indexer.run(IndexOptions(data_dir=data_dir, **options))
    finally:
        await resources.aclose()


def sql(query: str, *args: Any) -> list[asyncpg.Record]:
    async def go() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(plain_dsn(SEARCH_DB_URL))
        try:
            return await conn.fetch(query, *args)
        finally:
            await conn.close()

    return asyncio.run(go())


@pytest.fixture(scope="module")
def corpus_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write(tmp_path_factory.mktemp("corpus"))


@pytest.fixture(scope="module")
def first_index(corpus_dir: Path) -> IndexResult:
    """Fresh schema + empty Qdrant test alias, then one full index run."""
    asyncio.run(_ensure_database(SEARCH_DB_URL))
    config = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", SEARCH_DB_URL)
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    async def reset() -> None:
        resources = Resources.create(settings())
        try:
            await _drop_test_collections(resources)
        finally:
            await resources.aclose()

    asyncio.run(reset())
    return asyncio.run(run_indexer(corpus_dir))


@pytest.fixture(scope="module")
def client(first_index: IndexResult) -> Iterator[TestClient]:
    with TestClient(create_app(settings())) as test_client:
        yield test_client


def search(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post("/api/v1/search", json=body)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


def article_ids(body: dict[str, Any]) -> list[str]:
    return [r["article"]["article_id"] for r in body["results"]]


# --- indexer --------------------------------------------------------------------------------


def test_first_index(first_index: IndexResult) -> None:
    assert first_index.collection == f"{ALIAS}__0.0.0-fake"
    assert first_index.switched
    assert first_index.previous_collection is None
    assert first_index.points == 16
    assert (first_index.documents, first_index.articles) == (6, 14)
    assert first_index.pg_articles.inserted == 14
    state = sql("SELECT * FROM index_state WHERE collection = $1", first_index.collection)[0]
    assert state["index_compat_id"] == "fake"
    assert state["points_count"] == 16
    job = sql("SELECT * FROM index_jobs WHERE job_id = $1", first_index.job_id)[0]
    assert job["status"] == "succeeded"
    assert job["progress"] == 1.0
    assert job["collection"] == first_index.collection


def test_reindex_same_version_builds_next_to_live_collection(
    first_index: IndexResult, corpus_dir: Path
) -> None:
    result = asyncio.run(run_indexer(corpus_dir))
    assert result.collection.startswith(f"{ALIAS}__0.0.0-fake__")
    assert result.previous_collection == first_index.collection
    assert result.pg_articles.unchanged == 14  # nothing changed in Postgres
    assert result.pg_articles.inserted == result.pg_articles.updated == 0
    # --no-switch builds a third collection and leaves the alias alone; nothing is deleted.
    second = asyncio.run(run_indexer(corpus_dir, switch_alias=False))
    assert not second.switched
    assert second.collection not in (first_index.collection, result.collection)
    assert second.previous_collection == result.collection

    async def names() -> set[str]:
        resources = Resources.create(settings())
        try:
            return {c.name for c in (await resources.qdrant.client.get_collections()).collections}
        finally:
            await resources.aclose()

    assert {first_index.collection, result.collection, second.collection} <= asyncio.run(names())


def test_bad_corpus_fails_job_and_keeps_alias(first_index: IndexResult, tmp_path: Path) -> None:
    write(tmp_path)
    (tmp_path / "chunks.parquet").unlink()

    async def alias() -> str | None:
        resources = Resources.create(settings())
        try:
            return await resources.qdrant.alias_target()
        finally:
            await resources.aclose()

    alias_before = asyncio.run(alias())
    before = sql("SELECT count(*) AS n FROM index_jobs WHERE status = 'failed'")[0]["n"]
    with pytest.raises(CorpusError):
        asyncio.run(run_indexer(tmp_path))
    after = sql("SELECT count(*) AS n FROM index_jobs WHERE status = 'failed'")[0]["n"]
    assert after == before + 1
    assert asyncio.run(alias()) == alias_before


def test_only_one_job_at_a_time(first_index: IndexResult, corpus_dir: Path) -> None:
    job_id = uuid.uuid4()
    sql("INSERT INTO index_jobs (job_id, status) VALUES ($1, 'running')", job_id)
    try:
        with pytest.raises(JobConflict):
            asyncio.run(run_indexer(corpus_dir))
    finally:
        sql("DELETE FROM index_jobs WHERE job_id = $1", job_id)


def test_cli(first_index: IndexResult, corpus_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings
    from indexer.__main__ import main

    for key, value in {
        "DATABASE_URL": SEARCH_DB_URL,
        "QDRANT_URL": TEST_QDRANT_URL,
        "QDRANT_ALIAS": ALIAS,
        "ML_SERVICE_URL": TEST_ML_SERVICE_URL,
        "MANIFEST_SOURCE": "service",
        "LOG_JSON": "false",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        assert asyncio.run(main(["--data-dir", str(corpus_dir), "--no-switch"])) == 0
        assert asyncio.run(main(["--data-dir", str(corpus_dir / "missing")])) == 1
    finally:
        get_settings.cache_clear()


# --- search ---------------------------------------------------------------------------------


def test_search_contract_shape(client: TestClient) -> None:
    body = search(client, query=QUERY_RU)
    assert body["lang"] == "ru"
    assert body["mode"] == "hybrid"
    assert body["degraded"] == []
    assert body["pipeline_version"] == "0.0.0-fake"
    assert set(body["timing_ms"]) >= {"embed", "retrieve", "fuse", "rerank", "total"}
    ids = article_ids(body)
    assert ids
    assert all(i.startswith("T000000000") and ":ru:" in i for i in ids)
    assert "T0000000001:ru:a114" in ids[:3]
    first = body["results"][0]
    assert first["score_type"] == "rerank"
    assert first["doc"]["status"] == "in_force"
    assert len(first["snippet"]) <= 300
    for h in first["highlights"]:
        assert 0 <= h["start"] < h["end"] <= len(first["snippet"])


def test_in_force_filter(client: TestClient) -> None:
    default = article_ids(search(client, query="заработная плата исключена статья", top_k=50))
    assert "T0000000001:ru:a53" not in default  # excluded article
    assert not any(i.startswith("T0000000003") for i in default)  # repealed act
    everything = article_ids(
        search(
            client,
            query="заработная плата исключена статья",
            top_k=50,
            filters={"in_force_only": False},
        )
    )
    assert "T0000000001:ru:a53" in everything
    assert any(i.startswith("T0000000003") for i in everything)


def test_doc_type_doc_id_and_date_filters(client: TestClient) -> None:
    laws = article_ids(
        search(
            client,
            query="заработная плата",
            filters={"doc_types": ["law"], "in_force_only": False},
        )
    )
    assert laws
    assert all(i.startswith("T0000000003") for i in laws)
    eco = article_ids(search(client, query="штраф", filters={"doc_ids": ["T0000000002"]}))
    assert eco == ["T0000000002:ru:a10"]
    recent = article_ids(
        search(client, query="штраф зарплата", top_k=50, filters={"date_from": "2020-01-01"})
    )
    assert recent
    assert all(i.startswith("T0000000002") for i in recent)


def test_kazakh_search(client: TestClient) -> None:
    body = search(client, query="Еңбек шартын бұзу негіздері")
    assert body["lang"] == "kk"
    ids = article_ids(body)
    assert ids
    assert all(":kk:" in i for i in ids)
    assert ids[0] == "T0000000001:kk:a52"


def test_keyword_mode(client: TestClient) -> None:
    body = search(client, query="экологических штраф", mode="keyword")
    assert {r["score_type"] for r in body["results"]} == {"fusion"}
    assert "rerank" not in body["timing_ms"]
    assert article_ids(body)[0] == "T0000000002:ru:a10"


def test_no_match_is_empty_not_error(client: TestClient) -> None:
    body = search(client, query="квантовая хромодинамика", mode="keyword")
    assert body["results"] == []


def test_query_is_logged(client: TestClient) -> None:
    session = "11111111-2222-4333-8444-555555555555"
    response = client.post(
        "/api/v1/search",
        json={"query": "Сроки выплаты зарплаты"},
        headers={"X-Session-Id": session},
    )
    query_id = uuid.UUID(response.json()["query_id"])
    for _ in range(50):
        rows = sql("SELECT * FROM query_logs WHERE query_id = $1", query_id)
        if rows:
            break
        time.sleep(0.1)
    assert rows, "query log row was not written"
    row = rows[0]
    assert row["query_norm"] == "сроки выплаты зарплаты"
    assert row["client"] == "web"
    assert row["session_hash"]
    assert session not in row["session_hash"]
    assert row["result_count"] == len(response.json()["results"])
    assert row["search_ms"] is not None
    assert row["pipeline_version"] == "0.0.0-fake"


# --- articles and documents ------------------------------------------------------------------


def test_article_round_trip(client: TestClient) -> None:
    _, articles, _ = build()
    source = next(a for a in articles if a["article_id"] == "T0000000001:ru:a113")
    response = client.get("/api/v1/articles/T0000000001:ru:a113")
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == source["text"]  # verbatim, line breaks kept
    assert body["amendment_notes"] == source["amendment_notes"]
    assert body["article"]["has_amendments"] is True
    assert body["parallel_article_id"] == "T0000000001:kk:a113"
    assert body["prev_article_id"] == "T0000000001:ru:a53"
    assert body["next_article_id"] == "T0000000001:ru:a114"
    assert body["doc"]["doc_id"] == "T0000000001"
    first = client.get("/api/v1/articles/T0000000001:ru:a1").json()
    assert first["prev_article_id"] is None


def test_unknown_article_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/articles/T0000000001:ru:a999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_documents_list(client: TestClient) -> None:
    body = client.get("/api/v1/documents", params={"lang": "ru"}).json()
    assert body["total"] == 3
    assert {d["doc_id"] for d in body["items"]} == {"T0000000001", "T0000000002", "T0000000003"}
    assert all("article_count" in d for d in body["items"])
    laws = client.get("/api/v1/documents", params={"lang": "ru", "doc_type": "law"}).json()
    assert [d["doc_id"] for d in laws["items"]] == ["T0000000003"]
    found = client.get("/api/v1/documents", params={"lang": "kk", "q": "экологиялық"}).json()
    assert [d["doc_id"] for d in found["items"]] == ["T0000000002"]
    page = client.get("/api/v1/documents", params={"lang": "ru", "page": 2, "page_size": 2}).json()
    assert (page["page"], page["page_size"], page["total"], len(page["items"])) == (2, 2, 3, 1)
    weird = client.get("/api/v1/documents", params={"lang": "ru", "q": "100%_"}).json()
    assert weird["total"] == 0


def test_document_detail(client: TestClient) -> None:
    body = client.get("/api/v1/documents/T0000000001", params={"lang": "kk"}).json()
    assert body["short_title"] == "Сынақ ЕК"
    assert [t["article_id"] for t in body["toc"]] == [
        "T0000000001:kk:a1",
        "T0000000001:kk:a52",
        "T0000000001:kk:a53",
        "T0000000001:kk:a113",
        "T0000000001:kk:a114",
    ]
    missing = client.get("/api/v1/documents/T9999999999", params={"lang": "ru"})
    assert missing.status_code == 404


def test_index_built_by_another_process_is_used_at_once(corpus_dir: Path) -> None:
    """The CI sequence: search (no index) -> CLI indexes -> search, with the default cache TTL."""
    alias = "test_cache_chunks"
    cache_settings = settings().model_copy(update={"qdrant_alias": alias, "index_state_ttl_s": 30})

    async def with_resources(fn: Any) -> None:
        resources = Resources.create(cache_settings)
        try:
            await fn(resources)
        finally:
            await resources.aclose()

    async def reset(resources: Resources) -> None:
        client = resources.qdrant.client
        if any(a.alias_name == alias for a in (await client.get_aliases()).aliases):
            from qdrant_client import models as qm

            await client.update_collection_aliases(
                change_aliases_operations=[
                    qm.DeleteAliasOperation(delete_alias=qm.DeleteAlias(alias_name=alias))
                ]
            )
        for collection in (await client.get_collections()).collections:
            if collection.name.startswith(f"{alias}__"):
                await client.delete_collection(collection.name)

    async def index(resources: Resources) -> None:
        manifest = await resources.manifest.get()
        assert manifest is not None
        indexer = Indexer(resources.sessionmaker, resources.qdrant, resources.ml, manifest)
        await indexer.run(IndexOptions(data_dir=corpus_dir, prune=False))

    asyncio.run(with_resources(reset))
    with TestClient(create_app(cache_settings)) as api:
        before = api.post("/api/v1/search", json={"query": QUERY_RU})
        assert before.status_code == 503
        assert "No search index" in before.json()["error"]["message"]
        asyncio.run(with_resources(index))
        after = api.post("/api/v1/search", json={"query": QUERY_RU})
        assert after.status_code == 200, after.text
        assert after.json()["results"]


# --- answer (SSE) ---------------------------------------------------------------------------


def parse_sse(raw: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in raw.replace("\r\n", "\n").strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


def answer(client: TestClient, **body: Any) -> list[tuple[str, dict[str, Any]]]:
    with client.stream("POST", "/api/v1/answer", json=body) as response:
        assert response.status_code == 200, response.read()
        assert response.headers["content-type"].startswith("text/event-stream")
        return parse_sse(response.read().decode("utf-8"))


def wait_for_rows(query: str, *args: Any) -> list[asyncpg.Record]:
    for _ in range(50):
        rows = sql(query, *args)
        if rows:
            return rows
        time.sleep(0.1)
    return []


def test_answer_streams_and_is_persisted(client: TestClient) -> None:
    events = answer(client, query=QUERY_RU, context_top_k=3)
    names = [name for name, _ in events]
    assert names[0] == "sources"
    assert names[-1] == "done"
    assert names.count("token") >= 2
    sources = events[0][1]
    assert [s["ref"] for s in sources["sources"]] == [1, 2, 3]
    done = events[-1][1]
    assert "[1]" in done["text"]  # the fake ML's canned answer cites [1]
    assert done["citations"] == [1]
    assert done["grounded"] is True
    assert set(done["timing_ms"]) == {"search", "ttft", "total"}

    query_id = uuid.UUID(sources["query_id"])
    answer_rows = wait_for_rows("SELECT * FROM answers WHERE query_id = $1", query_id)
    assert answer_rows, "answer row was not written"
    row = answer_rows[0]
    assert str(row["answer_id"]) == done["answer_id"]
    assert row["status"] == "completed"
    assert row["text"] == done["text"]
    assert list(row["citations"]) == [1]
    log_row = sql("SELECT * FROM query_logs WHERE query_id = $1", query_id)[0]
    assert log_row["endpoint"] == "answer"
    assert log_row["has_answer"] is True


def test_answer_with_zero_results_does_not_call_the_llm(client: TestClient) -> None:
    events = answer(client, query="квантовая хромодинамика", mode="keyword")
    assert [name for name, _ in events] == ["sources", "done"]
    assert events[0][1]["sources"] == []
    done = events[1][1]
    assert done["grounded"] is False
    assert done["finish_reason"] == "no_results"
    assert "ttft" not in done["timing_ms"] or done["timing_ms"]["ttft"] is None


def test_answer_kazakh(client: TestClient) -> None:
    events = answer(client, query="Еңбек шартын бұзу негіздері")
    assert events[0][1]["lang"] == "kk"
    assert "[1]" in events[-1][1]["text"]


@pytest.fixture(scope="module")
def failing_ml() -> Iterator[str]:
    """A second fake-ml whose /generate fails (FAKE_ML_FAIL=generate)."""
    import os
    import subprocess
    import sys

    import httpx

    port = 8011
    env = {**os.environ, "FAKE_ML_FAIL": "generate", "FAKE_ML_DIM": "768"}
    proc = subprocess.Popen(  # noqa: S603 - fixed argv, test-only
        [sys.executable, "-m", "uvicorn", "dev.fake_ml.app:app", "--port", str(port)],
        cwd=REPO_ROOT / "backend",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(f"{url}/version", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_answer_generation_failure_sends_error_after_sources(
    first_index: IndexResult, failing_ml: str
) -> None:
    failing = settings().model_copy(update={"ml_service_url": failing_ml})
    with TestClient(create_app(failing)) as api:
        events = answer(api, query=QUERY_RU)
    assert events[0][0] == "sources"
    assert events[0][1]["sources"]
    assert events[-1] == (
        "error",
        {
            "code": "generation_unavailable",
            "message": "The answer generator is unavailable; the sources above are valid.",
        },
    )
    query_id = uuid.UUID(events[0][1]["query_id"])
    rows = wait_for_rows("SELECT status, error_code FROM answers WHERE query_id = $1", query_id)
    assert rows[0]["status"] == "error"
    assert rows[0]["error_code"] == "generation_unavailable"


# --- feedback ---------------------------------------------------------------------------------


def test_feedback_upsert_and_validation(client: TestClient) -> None:
    session = {"X-Session-Id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"}
    body = search(client, query="Сроки выплаты зарплаты")
    query_id = body["query_id"]
    article_id = body["results"][0]["article"]["article_id"]
    wait_for_rows("SELECT 1 FROM query_logs WHERE query_id = $1", uuid.UUID(query_id))

    for rating in (1, -1):
        response = client.post(
            "/api/v1/feedback",
            json={
                "query_id": query_id,
                "target": "result",
                "article_id": article_id,
                "rating": rating,
            },
            headers=session,
        )
        assert response.status_code == 204
        assert response.content == b""
    rows = sql("SELECT rating, article_id FROM feedback WHERE query_id = $1", uuid.UUID(query_id))
    assert [(r["rating"], r["article_id"]) for r in rows] == [(-1, article_id)]

    # Answer feedback is a separate row, and article_id is ignored for it.
    response = client.post(
        "/api/v1/feedback",
        json={
            "query_id": query_id,
            "target": "answer",
            "article_id": article_id,
            "rating": 1,
            "comment": "ok",
        },
        headers=session,
    )
    assert response.status_code == 204
    rows = sql(
        "SELECT target, article_id, comment FROM feedback WHERE query_id = $1 ORDER BY target",
        uuid.UUID(query_id),
    )
    assert [(r["target"], r["article_id"], r["comment"]) for r in rows] == [
        ("answer", None, "ok"),
        ("result", article_id, None),
    ]


def test_feedback_unknown_query_is_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/feedback",
        json={"query_id": str(uuid.uuid4()), "target": "answer", "rating": 1},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
