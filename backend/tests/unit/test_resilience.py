"""Degraded modes of SearchService: full-text fallback, circuit breakers, caches."""

from typing import Any

import pytest

from app.core.breaker import CircuitBreaker
from app.db.models import Article, Document
from app.schemas.ml import Manifest
from app.schemas.search import SearchFilters, SearchRequest
from app.services.index_info import ActiveIndex
from app.services.search import (
    Resilience,
    SearchBudgets,
    SearchContext,
    SearchError,
    SearchService,
)
from dev.fake_ml.app import fake_manifest
from tests.unit.test_search_service import (
    QUERY,
    ROWS,
    FakeIndex,
    FakeManifest,
    FakeMl,
    FakeStore,
    hits,
    lookup,
)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeFts:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, SearchFilters, int]] = []
        self.fail = False

    async def search(
        self, query: str, lang: str, filters: SearchFilters, limit: int
    ) -> list[tuple[Article, Document, float]]:
        self.calls.append((query, lang, filters, limit))
        if self.fail:
            raise ConnectionError("postgres down")
        article, document = ROWS["T0000000001:ru:a113"]
        return [(article, document, 0.42)]


def service_with(resilience: Resilience, **kwargs: Any) -> tuple[SearchService, FakeMl, FakeStore]:
    ml = kwargs.pop("ml", None) or FakeMl()
    store = kwargs.pop("store", None) or FakeStore(
        dense=hits("T0000000001:ru:a113:c0", "T0000000001:ru:a114:c0"),
        sparse=hits("T0000000001:ru:a114:c1", "T0000000001:ru:a113:c0"),
    )
    active = kwargs.pop("active", ActiveIndex("legal_chunks__0.0.0-fake", "fake", "0.0.0-fake"))
    service = SearchService(
        ml=ml,
        store=store,
        lookup=lookup,
        manifest=FakeManifest(Manifest.model_validate(fake_manifest())),
        index=FakeIndex(active),
        budgets=SearchBudgets(),
        resilience=resilience,
    )
    return service, ml, store


# --- circuit breaker --------------------------------------------------------------------------


def test_breaker_opens_after_n_failures_and_recovers_through_half_open() -> None:
    clock = Clock()
    breaker = CircuitBreaker("x", failures=3, reset_s=10, clock=clock)
    for _ in range(2):
        breaker.failure()
    assert breaker.state == "closed"
    assert breaker.allow()
    breaker.failure()
    assert breaker.state == "open"
    assert not breaker.allow()

    clock.now = 10
    assert breaker.state == "half-open"
    assert breaker.allow()  # one trial call
    assert not breaker.allow()  # the others still wait
    breaker.failure()  # the trial failed: open again, for a full reset period
    assert breaker.state == "open"

    clock.now = 20
    assert breaker.allow()
    breaker.success()
    assert breaker.state == "closed"
    assert breaker.allow()


def test_a_success_resets_the_failure_count() -> None:
    breaker = CircuitBreaker("x", failures=2, reset_s=10)
    breaker.failure()
    breaker.success()
    breaker.failure()
    assert breaker.state == "closed"


# --- full-text fallback -----------------------------------------------------------------------


@pytest.mark.parametrize("broken", ["embed", "store", "no_index", "incompatible"])
async def test_semantic_failure_falls_back_to_full_text(broken: str) -> None:
    fts = FakeFts()
    ml, kwargs = FakeMl(), {}
    if broken == "embed":
        ml.fail_embed = True
    elif broken == "store":
        store = FakeStore([], [])
        store.fail = True
        kwargs["store"] = store
    elif broken == "no_index":
        kwargs["active"] = ActiveIndex(None, None, None)
    else:
        kwargs["active"] = ActiveIndex("legal_chunks__old", "other-models", "0.0.1")
    service, _, _ = service_with(Resilience(fts=fts), ml=ml, **kwargs)

    request = SearchRequest(query=QUERY, top_k=5)
    outcome = await service.search(request, SearchContext())
    response = outcome.response
    assert response.degraded == ["semantic"]
    assert [r.article.article_id for r in response.results] == ["T0000000001:ru:a113"]
    assert response.results[0].score_type == "fts"
    assert response.results[0].score == 0.42
    assert response.results[0].snippet
    assert fts.calls == [(QUERY, "ru", request.filters, 5)]
    # /answer reuses the items: the generator gets article text as context
    assert outcome.items[0].chunk_text
    assert outcome.log_values["degraded"] == ["semantic"]


async def test_fallback_failure_is_503() -> None:
    fts, ml = FakeFts(), FakeMl()
    fts.fail = True
    ml.fail_embed = True
    service, _, _ = service_with(Resilience(fts=fts), ml=ml)
    with pytest.raises(SearchError) as info:
        await service.search(SearchRequest(query=QUERY), SearchContext())
    assert info.value.status_code == 503


async def test_open_ml_circuit_skips_the_ml_service_and_recovers() -> None:
    clock, fts, ml = Clock(), FakeFts(), FakeMl()
    breaker = CircuitBreaker("ml_embed", failures=2, reset_s=30, clock=clock)
    service, _, _ = service_with(Resilience(fts=fts, ml_breaker=breaker), ml=ml)
    request, ctx = SearchRequest(query=QUERY), SearchContext()

    ml.fail_embed = True
    for _ in range(2):
        assert (await service.search(request, ctx)).response.degraded == ["semantic"]
    assert breaker.state == "open"
    assert len(ml.embed_calls) == 2

    # Open: the dead service is not called at all (no timeout is paid).
    assert (await service.search(request, ctx)).response.degraded == ["semantic"]
    assert len(ml.embed_calls) == 2

    # After the reset period one trial call goes through; the service is back.
    clock.now = 30
    ml.fail_embed = False
    assert (await service.search(request, ctx)).response.degraded == []
    assert breaker.state == "closed"


async def test_open_rerank_circuit_returns_fused_order_without_calling_rerank() -> None:
    ml = FakeMl()
    breaker = CircuitBreaker("ml_rerank", failures=1, reset_s=30, clock=Clock())
    service, _, _ = service_with(Resilience(rerank_breaker=breaker), ml=ml)
    request, ctx = SearchRequest(query=QUERY), SearchContext()

    ml.fail_rerank = True
    assert (await service.search(request, ctx)).response.degraded == ["rerank"]
    assert breaker.state == "open"
    assert (await service.search(request, ctx)).response.degraded == ["rerank"]
    assert len(ml.rerank_calls) == 1


# --- caches -----------------------------------------------------------------------------------


async def test_repeated_search_is_served_from_the_cache_with_a_new_query_id() -> None:
    service, ml, store = service_with(Resilience(cache_ttl_s=60))
    request, ctx = SearchRequest(query=QUERY), SearchContext()
    first = await service.search(request, ctx)
    second = await service.search(request, ctx)
    assert len(ml.embed_calls) == 1
    assert store.dense_calls == 1
    assert second.response.query_id != first.response.query_id
    assert second.response.results == first.response.results
    assert set(second.response.timing_ms) == {"total"}
    assert second.log_values["query_id"] == second.response.query_id


async def test_cache_key_covers_filters_mode_and_top_k() -> None:
    service, ml, _ = service_with(Resilience(cache_ttl_s=60))
    ctx = SearchRequest(query=QUERY), SearchContext()
    await service.search(*ctx)
    await service.search(SearchRequest(query=QUERY, top_k=3), SearchContext())
    await service.search(SearchRequest(query=QUERY, mode="keyword"), SearchContext())
    await service.search(
        SearchRequest(query=QUERY, filters=SearchFilters(doc_ids=["T0000000001"])), SearchContext()
    )
    # Four different searches ran; the query embedding was reused where the mode allowed it.
    assert len(ml.embed_calls) == 2  # hybrid (dense + sparse) and keyword (sparse only)


async def test_degraded_responses_are_not_cached() -> None:
    ml = FakeMl()
    ml.fail_rerank = True
    service, _, store = service_with(Resilience(cache_ttl_s=60), ml=ml)
    request, ctx = SearchRequest(query=QUERY), SearchContext()
    assert (await service.search(request, ctx)).response.degraded == ["rerank"]
    ml.fail_rerank = False
    assert (await service.search(request, ctx)).response.degraded == []
    assert store.dense_calls == 2
