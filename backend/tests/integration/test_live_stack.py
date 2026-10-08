"""The real app against real postgres + qdrant + fake-ml: health, version, request id."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings
from tests.integration.conftest import TEST_ML_SERVICE_URL, TEST_QDRANT_URL

pytestmark = pytest.mark.integration


@pytest.fixture
def live_client(database_url: str) -> Iterator[TestClient]:
    settings = make_settings(
        database_url=database_url,
        qdrant_url=TEST_QDRANT_URL,
        ml_service_url=TEST_ML_SERVICE_URL,
        manifest_source="service",
        health_timeout_s=5,
    )
    with TestClient(create_app(settings)) as client:
        yield client


def test_health_all_components_ok(live_client: TestClient) -> None:
    response = live_client.get("/api/v1/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["components"] == {
        "database": "ok",
        "qdrant": "ok",
        "ml_service": "ok",
        "llm": "ok",
    }
    assert body["status"] == "ok"
    assert body["pipeline_version"] == "0.0.0-fake"


def test_version_live(live_client: TestClient) -> None:
    body = live_client.get("/api/v1/version").json()
    assert body["pipeline_version"] == "0.0.0-fake"
    assert body["index_collection"] is None  # nothing indexed yet (BE-02)


def test_health_reports_unreachable_ml(database_url: str) -> None:
    settings = make_settings(
        database_url=database_url,
        qdrant_url=TEST_QDRANT_URL,
        ml_service_url="http://127.0.0.1:9",  # nothing listens here
        health_timeout_s=2,
    )
    with TestClient(create_app(settings)) as client:
        body = client.get("/api/v1/health").json()
    assert body["components"]["ml_service"] == "down"
    assert body["components"]["llm"] == "unavailable"
    assert body["status"] == "degraded"
    assert body["pipeline_version"] is None
