"""IndexInfoProvider caching: usable states are cached, "no index" never is."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import index_info
from app.services.index_info import IndexInfoProvider


class FakeStore:
    def __init__(self, target: str | None) -> None:
        self.target = target
        self.calls = 0

    async def alias_target(self) -> str | None:
        self.calls += 1
        return self.target


def fake_sessionmaker() -> Any:
    @asynccontextmanager
    async def session() -> Any:
        yield None

    return session


@pytest.fixture
def states(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    rows: dict[str, Any] = {}

    async def get_index_state(_: Any, collection: str) -> Any:
        return rows.get(collection)

    monkeypatch.setattr(index_info.repo, "get_index_state", get_index_state)
    return rows


async def test_no_index_is_not_cached(states: dict[str, Any]) -> None:
    store = FakeStore(None)
    provider = IndexInfoProvider(store, fake_sessionmaker(), ttl_s=30)  # type: ignore[arg-type]
    assert (await provider.get()).collection is None
    # Another process builds the index and switches the alias.
    store.target = "legal_chunks__1.0.0"
    states["legal_chunks__1.0.0"] = SimpleNamespace(index_compat_id="c1", pipeline_version="1.0.0")
    active = await provider.get()
    assert active.collection == "legal_chunks__1.0.0"
    assert active.compatible_with("c1")


async def test_usable_state_is_cached_until_refresh(states: dict[str, Any]) -> None:
    store = FakeStore("legal_chunks__1.0.0")
    states["legal_chunks__1.0.0"] = SimpleNamespace(index_compat_id="c1", pipeline_version="1.0.0")
    provider = IndexInfoProvider(store, fake_sessionmaker(), ttl_s=30)  # type: ignore[arg-type]
    await provider.get()
    await provider.get()
    assert store.calls == 1
    await provider.get(refresh=True)
    assert store.calls == 2
    provider.invalidate()
    await provider.get()
    assert store.calls == 3


async def test_alias_without_state_row_is_not_cached(states: dict[str, Any]) -> None:
    store = FakeStore("legal_chunks__orphan")
    provider = IndexInfoProvider(store, fake_sessionmaker(), ttl_s=30)  # type: ignore[arg-type]
    active = await provider.get()
    assert active.collection == "legal_chunks__orphan"
    assert not active.compatible_with("c1")
    await provider.get()
    assert store.calls == 2
