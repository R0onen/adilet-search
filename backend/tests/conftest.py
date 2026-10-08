from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_health_service, get_manifest_provider, get_qdrant_store
from app.core.config import Settings
from app.main import create_app
from app.schemas.health import Components
from app.schemas.ml import Manifest
from dev.fake_ml.app import fake_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"

ALL_OK = Components(database="ok", qdrant="ok", ml_service="ok", llm="ok")


class FakeHealth:
    def __init__(self, components: Components = ALL_OK) -> None:
        self.value = components

    async def components(self) -> Components:
        return self.value


class FakeManifest:
    def __init__(self, manifest: Manifest | None) -> None:
        self.value = manifest

    async def get(self) -> Manifest | None:
        return self.value


class FakeQdrant:
    def __init__(self, collection: str | None = "legal_chunks__0.0.0-fake", fail: bool = False):
        self.collection = collection
        self.fail = fail

    async def alias_target(self) -> str | None:
        if self.fail:
            raise ConnectionError("qdrant down")
        return self.collection


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "log_json": False,
        "git_sha": "abc1234",
        "app_version": "0.1.0",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def fakes() -> dict[str, object]:
    return {
        "health": FakeHealth(),
        "manifest": FakeManifest(Manifest.model_validate(fake_manifest())),
        "qdrant": FakeQdrant(),
    }


@pytest.fixture
def app(settings: Settings, fakes: dict[str, object]) -> FastAPI:
    application = create_app(settings)
    application.dependency_overrides[get_health_service] = lambda: fakes["health"]
    application.dependency_overrides[get_manifest_provider] = lambda: fakes["manifest"]
    application.dependency_overrides[get_qdrant_store] = lambda: fakes["qdrant"]
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
