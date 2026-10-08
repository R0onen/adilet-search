"""The fake ML service obeys contracts/ml_service.md (shapes and invariants)."""

import json
import math
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.schemas.ml import EmbedResponse, GenerateDone, Manifest, MlHealth, RerankResponse
from dev.fake_ml.app import app

QUESTION = "Ответственность работодателя за задержку зарплаты"
SOURCE = {"ref": 1, "article_id": "K1500000414:ru:a113", "title": "Статья 113", "text": "…"}


@pytest.fixture
def ml(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("FAKE_ML_DIM", "64")
    monkeypatch.setenv("FAKE_ML_TOKEN_DELAY_MS", "0")
    monkeypatch.delenv("FAKE_ML_FAIL", raising=False)
    with TestClient(app) as client:
        yield client


def parse_sse(raw: str) -> list[tuple[str, dict[str, object]]]:
    events = []
    for block in raw.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_health_and_version(ml: TestClient) -> None:
    health = MlHealth.model_validate(ml.get("/health").json())
    assert health.status == "ok"
    assert set(health.components) == {"embedder", "sparse", "reranker", "generator"}
    manifest = Manifest.model_validate(ml.get("/version").json())
    assert manifest.index_compat_id == "fake"
    assert manifest.embedder.dim == 64


def test_embed_shapes(ml: TestClient) -> None:
    texts = [QUESTION, "Трудовой кодекс. Статья 113. Сроки выплаты заработной платы", ""]
    response = ml.post("/embed", json={"texts": texts, "kind": "passage"})
    assert response.status_code == 200
    body = EmbedResponse.model_validate(response.json())
    assert body.dim == 64
    assert body.dense is not None
    assert body.sparse is not None
    assert len(body.dense) == len(body.sparse) == len(body.truncated) == 3
    for vector in body.dense:
        assert len(vector) == 64
        assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-5)
    for sparse in body.sparse:
        assert sparse.indices == sorted(set(sparse.indices))
        assert all(0 <= i < 2**32 for i in sparse.indices)
        assert sparse.values == [1.0] * len(sparse.indices)
    assert body.sparse[2].indices == []


def test_embed_is_deterministic_and_similarity_follows_shared_words(ml: TestClient) -> None:
    texts = ["задержка заработной платы", "задержка заработной платы работодателем", "налог"]
    first = ml.post("/embed", json={"texts": texts, "kind": "query"}).json()
    second = ml.post("/embed", json={"texts": texts, "kind": "query"}).json()
    assert first["dense"] == second["dense"]
    dense = first["dense"]
    assert cosine(dense[0], dense[1]) > cosine(dense[0], dense[2])


def test_embed_optional_outputs(ml: TestClient) -> None:
    body = ml.post("/embed", json={"texts": ["a"], "kind": "query", "return_dense": False}).json()
    assert body["dense"] is None
    assert body["sparse"] is not None
    body = ml.post("/embed", json={"texts": ["a"], "kind": "query", "return_sparse": False}).json()
    assert body["sparse"] is None


def test_embed_truncation_flag(ml: TestClient) -> None:
    long_text = " ".join(f"w{i}" for i in range(600))
    body = ml.post("/embed", json={"texts": [long_text, "short"], "kind": "passage"}).json()
    assert body["truncated"] == [True, False]


@pytest.mark.parametrize(
    "payload",
    [
        {"texts": ["x"] * 129, "kind": "passage"},
        {"texts": [], "kind": "passage"},
        {"texts": ["x"], "kind": "document"},
        {"texts": ["x" * 8001], "kind": "passage"},
    ],
)
def test_embed_limits(ml: TestClient, payload: dict[str, object]) -> None:
    response = ml.post("/embed", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_rerank_sorted_by_score(ml: TestClient) -> None:
    candidates = [
        {"id": "a", "text": "налоговый кодекс"},
        {"id": "b", "text": "задержка заработной платы работодателем"},
        {"id": "c", "text": "задержка"},
    ]
    response = ml.post(
        "/rerank", json={"query": "задержка заработной платы", "candidates": candidates}
    )
    body = RerankResponse.model_validate(response.json())
    scores = [r.score for r in body.results]
    assert scores == sorted(scores, reverse=True)
    assert body.results[0].id == "b"
    assert {r.id for r in body.results} == {"a", "b", "c"}


def test_rerank_top_n_and_limit(ml: TestClient) -> None:
    candidates = [{"id": str(i), "text": f"text {i}"} for i in range(5)]
    body = ml.post("/rerank", json={"query": "text", "candidates": candidates, "top_n": 2}).json()
    assert len(body["results"]) == 2
    too_many = [{"id": str(i), "text": "t"} for i in range(101)]
    assert ml.post("/rerank", json={"query": "t", "candidates": too_many}).status_code == 422


@pytest.mark.parametrize("lang", ["ru", "kk"])
def test_generate_stream(ml: TestClient, lang: str) -> None:
    payload = {"question": QUESTION, "lang": lang, "sources": [SOURCE], "stream": True}
    with ml.stream("POST", "/generate", json=payload) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        events = parse_sse(response.read().decode("utf-8"))
    names = [name for name, _ in events]
    assert names[-1] == "done"
    assert set(names[:-1]) == {"token"}
    done = GenerateDone.model_validate(events[-1][1])
    assert "".join(str(data["text"]) for _, data in events[:-1]) == done.text
    assert "[1]" in done.text
    assert done.finish_reason == "stop"


def test_generate_non_streaming(ml: TestClient) -> None:
    payload = {"question": QUESTION, "lang": "ru", "sources": [SOURCE], "stream": False}
    done = GenerateDone.model_validate(ml.post("/generate", json=payload).json())
    assert "[1]" in done.text


def test_generate_limits(ml: TestClient) -> None:
    sources = [{**SOURCE, "ref": i} for i in range(1, 10)]
    payload = {"question": QUESTION, "lang": "ru", "sources": sources}
    assert ml.post("/generate", json=payload).status_code == 422
    payload = {"question": QUESTION, "lang": "ru", "sources": [SOURCE], "max_tokens": 1025}
    assert ml.post("/generate", json=payload).status_code == 422


def test_fail_modes(ml: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ML_FAIL", "rerank,generate")
    health = ml.get("/health").json()
    assert health["status"] == "degraded"
    assert health["components"]["reranker"] == "down"
    assert ml.post("/embed", json={"texts": ["a"], "kind": "query"}).status_code == 200
    rerank = ml.post("/rerank", json={"query": "a", "candidates": [{"id": "1", "text": "a"}]})
    assert rerank.status_code == 503
    assert rerank.json()["error"]["code"] == "internal_error"
    payload = {"question": QUESTION, "lang": "ru", "sources": [SOURCE]}
    with ml.stream("POST", "/generate", json=payload) as response:
        events = parse_sse(response.read().decode("utf-8"))
    assert events == [("error", {"code": "llm_unavailable", "message": "LLM unavailable"})]


def test_fail_all(ml: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ML_FAIL", "all")
    response = ml.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "down"
    assert ml.post("/embed", json={"texts": ["a"], "kind": "query"}).status_code == 503


def test_request_id_propagated(ml: TestClient) -> None:
    response = ml.get("/health", headers={"X-Request-Id": "abc-123-request"})
    assert response.headers["X-Request-Id"] == "abc-123-request"


def test_metrics(ml: TestClient) -> None:
    ml.get("/health")
    text = ml.get("/metrics").text
    assert 'ml_requests_total{endpoint="/health",status="200"}' in text
