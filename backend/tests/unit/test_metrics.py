from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_session
from app.core.config import Settings
from app.main import create_app


def test_metrics_use_route_templates_and_do_not_count_scrapes(
    client: TestClient, app: FastAPI
) -> None:
    app.dependency_overrides[get_session] = lambda: None
    client.get("/api/v1/articles/" + "a" * 129)
    client.get("/nonexistent-private-path")
    first = client.get("/metrics")
    second = client.get("/metrics")
    assert first.status_code == 200
    assert _http_series(first.text) == _http_series(second.text)
    assert 'route="/articles/{article_id}"' in first.text
    assert 'route="unmatched"' in first.text
    assert "a" * 129 not in first.text
    assert "nonexistent-private-path" not in first.text


def test_metrics_are_isolated_between_app_instances() -> None:
    settings = Settings(_env_file=None, environment="test")
    with TestClient(create_app(settings)) as first, TestClient(create_app(settings)) as second:
        first.get("/missing")
        assert 'status="404"' in _http_series(first.get("/metrics").text)
        assert 'status="404"' not in _http_series(second.get("/metrics").text)


def _http_series(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.startswith("adilet_http_"))
