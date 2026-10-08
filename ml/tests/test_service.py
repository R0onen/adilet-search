import json
import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adilet_ml.schemas import EmbedResponse, GenerateDone, MlHealth, RerankResponse
from adilet_ml.serving.app import app

MANIFEST = Path(__file__).parents[1] / "models/model_manifest.json"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("MODEL_MANIFEST_PATH", str(MANIFEST))
    monkeypatch.setenv("ADILET_ML_EMBEDDER_BACKEND", "hash")
    with TestClient(app) as test_client:
        yield test_client


def parse_sse(raw: str) -> list[tuple[str, dict[str, object]]]:
    events = []
    for block in raw.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def test_health_and_version(client: TestClient) -> None:
    health = MlHealth.model_validate(client.get("/health").json())
    assert health.status == "ok"
    assert health.components["embedder"] == "ok"
    manifest = client.get("/version").json()
    assert manifest["pipeline_version"] == "0.1.0-bootstrap"
    assert manifest["embedder"]["dim"] == 768


def test_embed_shape_and_determinism(client: TestClient) -> None:
    payload = {"texts": ["задержка заработной платы", "экологический штраф"], "kind": "query"}
    first = EmbedResponse.model_validate(client.post("/embed", json=payload).json())
    second = EmbedResponse.model_validate(client.post("/embed", json=payload).json())
    assert first.dense == second.dense
    assert first.sparse == second.sparse
    assert first.dim == 768
    assert first.dense is not None
    for vector in first.dense:
        assert len(vector) == 768
        assert math.isclose(math.sqrt(sum(value * value for value in vector)), 1.0, rel_tol=1e-5)


def test_embed_limits(client: TestClient) -> None:
    response = client.post("/embed", json={"texts": ["x" * 8001], "kind": "query"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_rerank(client: TestClient) -> None:
    payload = {
        "query": "задержка заработной платы",
        "candidates": [
            {"id": "bad", "text": "экологический штраф"},
            {"id": "good", "text": "ответственность за задержку заработной платы"},
        ],
    }
    body = RerankResponse.model_validate(client.post("/rerank", json=payload).json())
    assert [item.id for item in body.results] == ["good", "bad"]


def test_generate_stream_and_non_stream(client: TestClient) -> None:
    source = {
        "ref": 1,
        "article_id": "K1500000414:ru:a113",
        "title": "Статья 113",
        "text": "Заработная плата выплачивается работнику не реже одного раза в месяц.",
    }
    payload = {"question": "Когда платят зарплату?", "lang": "ru", "sources": [source]}
    with client.stream("POST", "/generate", json=payload) as response:
        events = parse_sse(response.read().decode("utf-8"))
    assert events[-1][0] == "done"
    done = GenerateDone.model_validate(events[-1][1])
    assert "[1]" in done.text
    non_stream = GenerateDone.model_validate(
        client.post("/generate", json={**payload, "stream": False}).json()
    )
    assert non_stream.text == done.text


def test_metrics(client: TestClient) -> None:
    client.get("/health")
    metrics = client.get("/metrics").text
    assert "ml_requests_total" in metrics
