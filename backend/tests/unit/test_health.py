import pytest
from fastapi.testclient import TestClient

from app.schemas.health import Components
from app.schemas.ml import MlHealth
from app.services.health import ml_statuses, overall_status
from tests.conftest import FakeHealth, FakeManifest, FakeQdrant


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "components": {"database": "ok", "qdrant": "ok", "ml_service": "ok", "llm": "ok"},
        "pipeline_version": "0.0.0-fake",
        "app_version": "0.1.0",
    }


def test_health_down_when_database_down(client: TestClient, fakes: dict[str, object]) -> None:
    fakes["health"] = FakeHealth(
        Components(database="down", qdrant="ok", ml_service="ok", llm="ok")
    )
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["status"] == "down"


@pytest.mark.parametrize(
    ("qdrant", "ml_service"), [("down", "ok"), ("ok", "down"), ("ok", "degraded")]
)
def test_health_degraded(
    client: TestClient, fakes: dict[str, object], qdrant: str, ml_service: str
) -> None:
    fakes["health"] = FakeHealth(
        Components(database="ok", qdrant=qdrant, ml_service=ml_service, llm="ok")  # type: ignore[arg-type]
    )
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_llm_does_not_affect_status(client: TestClient, fakes: dict[str, object]) -> None:
    fakes["health"] = FakeHealth(
        Components(database="ok", qdrant="ok", ml_service="ok", llm="unavailable")
    )
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["components"]["llm"] == "unavailable"


def test_health_without_manifest(client: TestClient, fakes: dict[str, object]) -> None:
    fakes["manifest"] = FakeManifest(None)
    body = client.get("/api/v1/health").json()
    assert body["pipeline_version"] is None


def test_version(client: TestClient) -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json() == {
        "app_version": "0.1.0",
        "git_sha": "abc1234",
        "pipeline_version": "0.0.0-fake",
        "index_collection": "legal_chunks__0.0.0-fake",
    }


def test_version_survives_qdrant_failure(client: TestClient, fakes: dict[str, object]) -> None:
    fakes["qdrant"] = FakeQdrant(fail=True)
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["index_collection"] is None


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (None, ("down", "unavailable")),
        ({"status": "down", "components": {}}, ("down", "unavailable")),
        (
            {
                "status": "ok",
                "components": {
                    "embedder": "ok",
                    "sparse": "ok",
                    "reranker": "ok",
                    "generator": "ok",
                },
            },
            ("ok", "ok"),
        ),
        # Generator down: ml-service reports degraded, but search still has every model.
        (
            {
                "status": "degraded",
                "components": {
                    "embedder": "ok",
                    "sparse": "ok",
                    "reranker": "ok",
                    "generator": "unavailable",
                },
            },
            ("ok", "unavailable"),
        ),
        (
            {
                "status": "degraded",
                "components": {"embedder": "ok", "sparse": "ok", "reranker": "down"},
            },
            ("degraded", "unavailable"),
        ),
    ],
)
def test_ml_statuses(body: dict[str, object] | None, expected: tuple[str, str]) -> None:
    health = MlHealth.model_validate(body) if body is not None else None
    assert ml_statuses(health) == expected


def test_overall_status() -> None:
    assert (
        overall_status(Components(database="ok", qdrant="ok", ml_service="ok", llm="down")) == "ok"
    )
    assert (
        overall_status(Components(database="down", qdrant="down", ml_service="down", llm="down"))
        == "down"
    )
