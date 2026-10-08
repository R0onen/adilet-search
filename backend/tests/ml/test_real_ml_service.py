"""Opt-in tests against the REAL ml-service (BE-02 task 6). Not run by default.

    TEST_ML_SERVICE_URL=http://127.0.0.1:8001 uv run pytest -m ml

Part 1 checks the running service against contracts/ml_service.md (works against fake-ml too,
which is how this file is kept honest in CI-less weeks). Part 2 indexes ML's `data/sample/`
with the real models into its own alias/database and checks that a TOR query finds the Labor
Code. It is skipped until `data/sample/` exists.

Also needs postgres + qdrant (`docker compose --profile dev up -d postgres qdrant`) for part 2;
the same TEST_DATABASE_URL / TEST_QDRANT_URL variables as the integration tests apply.
"""

import asyncio
import json
import math
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config

from app.schemas.ml import EmbedResponse, Manifest, MlHealth, RerankResponse
from app.state import Resources
from indexer.pipeline import Indexer, IndexOptions
from tests.conftest import REPO_ROOT, make_settings
from tests.integration.conftest import (
    TEST_DATABASE_URL,
    TEST_ML_SERVICE_URL,
    TEST_QDRANT_URL,
    _ensure_database,
)

pytestmark = pytest.mark.ml

SAMPLE_DIR = REPO_ROOT / "data" / "sample"
LABOR_CODE = "K1500000414"
ML_DB_URL = TEST_DATABASE_URL + "_ml"
ALIAS = "test_ml_chunks"


@pytest.fixture(scope="module")
def ml() -> httpx.Client:
    client = httpx.Client(base_url=TEST_ML_SERVICE_URL, timeout=120)
    try:
        client.get("/health")
    except httpx.HTTPError:
        pytest.skip(f"no ml-service at {TEST_ML_SERVICE_URL}")
    return client


@pytest.fixture(scope="module")
def manifest(ml: httpx.Client) -> Manifest:
    return Manifest.model_validate(ml.get("/version").json())


# --- part 1: the service obeys contracts/ml_service.md ---------------------------------------


def test_health_shape(ml: httpx.Client) -> None:
    response = ml.get("/health")
    health = MlHealth.model_validate(response.json())
    assert response.status_code == (503 if health.status == "down" else 200)
    assert {"embedder", "sparse", "reranker", "generator"} <= set(health.components)


def test_manifest(manifest: Manifest) -> None:
    assert manifest.pipeline_version
    assert manifest.index_compat_id
    assert manifest.embedder.dim > 0
    assert manifest.retrieval.rerank_top_n <= 100


def test_embed_query_and_passage(ml: httpx.Client, manifest: Manifest) -> None:
    texts = ["Основания расторжения трудового договора", "Еңбек шартын бұзу негіздері"]
    for kind in ("query", "passage"):
        body = EmbedResponse.model_validate(
            ml.post("/embed", json={"texts": texts, "kind": kind}).json()
        )
        assert body.dim == manifest.embedder.dim
        assert body.dense is not None
        assert body.sparse is not None
        assert len(body.dense) == len(body.sparse) == len(body.truncated) == 2
        for vector in body.dense:
            assert len(vector) == body.dim
            assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-3)
        for sparse in body.sparse:
            assert len(sparse.indices) == len(sparse.values) > 0
            assert all(0 <= i < 2**32 for i in sparse.indices)


def test_rerank_sorted(ml: httpx.Client) -> None:
    candidates = [
        {"id": "a", "text": "Налоговый кодекс. Статья 1. Налоговое законодательство"},
        {"id": "b", "text": "Трудовой кодекс. Статья 52. Расторжение трудового договора"},
    ]
    body = RerankResponse.model_validate(
        ml.post(
            "/rerank",
            json={"query": "Основания расторжения трудового договора", "candidates": candidates},
        ).json()
    )
    scores = [r.score for r in body.results]
    assert scores == sorted(scores, reverse=True)
    assert {r.id for r in body.results} == {"a", "b"}


def test_generate_stream_events(ml: httpx.Client) -> None:
    health = MlHealth.model_validate(ml.get("/health").json())
    if health.components.get("generator") != "ok":
        pytest.skip("generator (LLM) is not available")
    payload = {
        "question": "Какие основания расторжения трудового договора?",
        "lang": "ru",
        "sources": [
            {
                "ref": 1,
                "article_id": f"{LABOR_CODE}:ru:a52",
                "title": "Трудовой кодекс РК. Статья 52. Расторжение трудового договора",
                "text": "Трудовой договор может быть расторгнут по инициативе работодателя.",
            }
        ],
        "max_tokens": 64,
        "stream": True,
    }
    events: list[tuple[str, dict[str, Any]]] = []
    with ml.stream("POST", "/generate", json=payload) as response:
        event = "message"
        for line in response.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                events.append((event, json.loads(line[5:].strip())))
    names = [name for name, _ in events]
    assert names[-1] in ("done", "error")
    if names[-1] == "done":
        assert "token" in names
        assert events[-1][1]["model_version"]


# --- part 2: the real models find the Labor Code ---------------------------------------------


@pytest.mark.skipif(not (SAMPLE_DIR / "chunks.parquet").exists(), reason="no data/sample yet")
def test_tor_query_finds_labor_code(ml: httpx.Client, manifest: Manifest) -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    asyncio.run(_ensure_database(ML_DB_URL))
    config = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", ML_DB_URL)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    settings = make_settings(
        database_url=ML_DB_URL,
        qdrant_url=TEST_QDRANT_URL,
        qdrant_alias=ALIAS,
        ml_service_url=TEST_ML_SERVICE_URL,
        ml_timeout_s=120,
        index_state_ttl_s=0,
    )

    async def index() -> float:
        resources = Resources.create(settings)
        try:
            started = time.perf_counter()
            indexer = Indexer(resources.sessionmaker, resources.qdrant, resources.ml, manifest)
            await indexer.run(IndexOptions(data_dir=Path(SAMPLE_DIR), batch_size=32))
            return time.perf_counter() - started
        finally:
            await resources.aclose()

    seconds = asyncio.run(index())
    print(f"indexed data/sample with {manifest.pipeline_version} in {seconds:.1f}s")

    with TestClient(create_app(settings)) as api:
        for query in (
            "Основания расторжения трудового договора",
            "Ответственность работодателя за задержку зарплаты",
        ):
            body = api.post("/api/v1/search", json={"query": query, "top_k": 5}).json()
            print(query, [(r["article"]["article_id"], r["score"]) for r in body["results"]])
            print("timing_ms", body["timing_ms"])
            assert any(r["doc"]["doc_id"] == LABOR_CODE for r in body["results"]), body
