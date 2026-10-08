"""SearchService orchestration with fakes: modes, rerank degradation, failures, assembly, logs."""

from typing import Any, Literal

import pytest

from app.core.errors import APIError
from app.db.models import Article, Document
from app.schemas.ml import (
    EmbedResponse,
    Manifest,
    RerankCandidate,
    RerankResponse,
    RerankScore,
    SparseVector,
)
from app.schemas.search import SearchRequest
from app.services.index_info import ActiveIndex
from app.services.ml_client import MlUnavailable
from app.services.qdrant_store import Hit
from app.services.search import SearchBudgets, SearchContext, SearchError, SearchService
from dev.fake_ml.app import fake_manifest
from dev.sample_corpus import build
from indexer.pipeline import chunk_payload

DOCUMENTS, ARTICLES, CHUNKS = build()
ARTICLE_COLUMNS = {c.name for c in Article.__table__.columns} - {"tsv", "created_at", "updated_at"}
DOCUMENT_COLUMNS = {c.name for c in Document.__table__.columns} - {"created_at", "updated_at"}
ROWS = {
    a["article_id"]: (
        Article(**{k: v for k, v in a.items() if k in ARTICLE_COLUMNS}),
        Document(
            **{
                k: v
                for k, v in next(
                    d for d in DOCUMENTS if (d["doc_id"], d["lang"]) == (a["doc_id"], a["lang"])
                ).items()
                if k in DOCUMENT_COLUMNS
            }
        ),
    )
    for a in ARTICLES
}
PAYLOADS = {c["chunk_id"]: chunk_payload(c) for c in CHUNKS}


def hits(*chunk_ids: str) -> list[Hit]:
    return [Hit(chunk_id=c, payload=PAYLOADS[c]) for c in chunk_ids]


class FakeMl:
    def __init__(self) -> None:
        self.embed_calls: list[dict[str, Any]] = []
        self.rerank_calls: list[list[RerankCandidate]] = []
        self.fail_embed = False
        self.fail_rerank = False
        self.rerank_scores: dict[str, float] = {}

    async def embed(
        self,
        texts: list[str],
        kind: Literal["query", "passage"],
        *,
        dense: bool = True,
        sparse: bool = True,
        timeout_s: float | None = None,
    ) -> EmbedResponse:
        self.embed_calls.append({"texts": texts, "kind": kind, "dense": dense, "sparse": sparse})
        if self.fail_embed:
            raise MlUnavailable("/embed", "connection")
        return EmbedResponse(
            dense=[[1.0, 0.0]] if dense else None,
            sparse=[SparseVector(indices=[1, 2], values=[1.0, 1.0])] if sparse else None,
            dim=2,
            truncated=[False],
            model_version="test",
        )

    async def rerank(
        self, query: str, candidates: list[RerankCandidate], *, timeout_s: float | None = None
    ) -> RerankResponse:
        self.rerank_calls.append(candidates)
        if self.fail_rerank:
            raise MlUnavailable("/rerank", "timeout")
        results = [
            RerankScore(id=c.id, score=self.rerank_scores.get(c.id, 0.0)) for c in candidates
        ]
        results.sort(key=lambda r: -r.score)
        return RerankResponse(results=results, model_version="test")


class FakeStore:
    def __init__(self, dense: list[Hit], sparse: list[Hit]) -> None:
        self.dense = dense
        self.sparse = sparse
        self.dense_calls = 0
        self.sparse_calls = 0
        self.filters: list[Any] = []
        self.fail = False

    async def search_dense(self, vector: list[float], query_filter: Any, limit: int) -> list[Hit]:
        self.dense_calls += 1
        self.filters.append(query_filter)
        if self.fail:
            raise ConnectionError("qdrant down")
        return self.dense[:limit]

    async def search_sparse(
        self, indices: list[int], values: list[float], query_filter: Any, limit: int
    ) -> list[Hit]:
        self.sparse_calls += 1
        if self.fail:
            raise ConnectionError("qdrant down")
        return self.sparse[:limit]


class FakeManifest:
    def __init__(self, manifest: Manifest | None) -> None:
        self.value = manifest

    async def get(self) -> Manifest | None:
        return self.value


class FakeIndex:
    def __init__(self, active: ActiveIndex, after_refresh: ActiveIndex | None = None) -> None:
        self.value = active
        self.after_refresh = after_refresh
        self.refreshes = 0

    async def get(self, refresh: bool = False) -> ActiveIndex:
        if refresh:
            self.refreshes += 1
            if self.after_refresh is not None:
                self.value = self.after_refresh
        return self.value


async def lookup(article_ids: list[str]) -> dict[str, tuple[Article, Document]]:
    return {a: ROWS[a] for a in article_ids if a in ROWS}


def make_service(
    ml: FakeMl | None = None,
    store: FakeStore | None = None,
    manifest: Manifest | None = None,
    active: ActiveIndex | None = None,
    lookup_fn: Any = lookup,
) -> tuple[SearchService, FakeMl, FakeStore]:
    ml = ml or FakeMl()
    store = store or FakeStore(
        dense=hits("T0000000001:ru:a113:c0", "T0000000001:ru:a114:c0", "T0000000001:ru:a1:c0"),
        sparse=hits("T0000000001:ru:a114:c1", "T0000000001:ru:a113:c0", "T0000000002:ru:a10:c0"),
    )
    service = SearchService(
        ml=ml,
        store=store,
        lookup=lookup_fn,
        manifest=FakeManifest(manifest or Manifest.model_validate(fake_manifest())),
        index=FakeIndex(active or ActiveIndex("legal_chunks__0.0.0-fake", "fake", "0.0.0-fake")),
        budgets=SearchBudgets(),
    )
    return service, ml, store


QUERY = "Ответственность работодателя за задержку зарплаты"


async def test_hybrid_search_reranks_and_assembles() -> None:
    service, ml, store = make_service()
    ml.rerank_scores = {"T0000000001:ru:a114": 5.0, "T0000000001:ru:a113": 1.0}
    outcome = await service.search(SearchRequest(query=QUERY), SearchContext())
    response = outcome.response
    assert response.lang == "ru"
    assert response.mode == "hybrid"
    assert response.degraded == []
    assert response.pipeline_version == "0.0.0-fake"
    ranked = [r.article.article_id for r in response.results]
    assert ranked[:2] == ["T0000000001:ru:a114", "T0000000001:ru:a113"]
    assert response.total_candidates == len(ranked) == 4
    first = response.results[0]
    assert first.rank == 1
    assert first.score_type == "rerank"
    assert first.score == 5.0
    assert first.doc.short_title == "Тестовый ТК"
    assert len(first.snippet) <= 300
    assert first.highlights
    assert ml.embed_calls == [{"texts": [QUERY], "kind": "query", "dense": True, "sparse": True}]
    assert (store.dense_calls, store.sparse_calls) == (1, 1)
    # rerank got the best chunk's text_for_embedding
    sent = {c.id: c.text for c in ml.rerank_calls[0]}
    assert sent["T0000000001:ru:a113"].startswith("Тестовый ТК. Статья 113.")
    timing = response.timing_ms
    assert set(timing) == {"embed", "retrieve", "fuse", "rerank", "total"}


async def test_semantic_mode_skips_sparse() -> None:
    service, ml, store = make_service()
    outcome = await service.search(SearchRequest(query=QUERY, mode="semantic"), SearchContext())
    assert ml.embed_calls[0]["sparse"] is False
    assert store.sparse_calls == 0
    assert outcome.response.results[0].score_type == "rerank"


async def test_keyword_mode_skips_dense_and_rerank() -> None:
    service, ml, store = make_service()
    outcome = await service.search(SearchRequest(query=QUERY, mode="keyword"), SearchContext())
    assert ml.embed_calls[0]["dense"] is False
    assert store.dense_calls == 0
    assert ml.rerank_calls == []
    results = outcome.response.results
    assert [r.article.article_id for r in results] == [
        "T0000000001:ru:a114",
        "T0000000001:ru:a113",
        "T0000000002:ru:a10",
    ]
    assert {r.score_type for r in results} == {"fusion"}
    assert "rerank" not in outcome.response.timing_ms


async def test_rerank_failure_degrades_to_fused_order() -> None:
    service, ml, _ = make_service()
    ml.fail_rerank = True
    outcome = await service.search(SearchRequest(query=QUERY), SearchContext())
    assert outcome.response.degraded == ["rerank"]
    assert {r.score_type for r in outcome.response.results} == {"fusion"}
    # Fused order: a113 (dense 1 + sparse 2) ranks first.
    assert outcome.response.results[0].article.article_id == "T0000000001:ru:a113"
    assert outcome.log_values["degraded"] == ["rerank"]


async def test_top_k_and_missing_db_rows() -> None:
    async def partial_lookup(ids: list[str]) -> dict[str, tuple[Article, Document]]:
        rows = await lookup(ids)
        rows.pop("T0000000001:ru:a113", None)
        return rows

    service, _, _ = make_service(lookup_fn=partial_lookup)
    outcome = await service.search(SearchRequest(query=QUERY, top_k=2), SearchContext())
    ids = [r.article.article_id for r in outcome.response.results]
    assert len(ids) == 2
    assert "T0000000001:ru:a113" not in ids
    assert [r.rank for r in outcome.response.results] == [1, 2]


async def test_zero_results() -> None:
    service, ml, _ = make_service(store=FakeStore([], []))
    outcome = await service.search(SearchRequest(query=QUERY), SearchContext())
    assert outcome.response.results == []
    assert outcome.response.total_candidates == 0
    assert ml.rerank_calls == []
    assert outcome.log_values["zero_results"] is True
    assert outcome.log_values["top_article_id"] is None


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        ("no_manifest", "manifest not loaded"),
        ("no_index", "No search index"),
        ("incompatible", "reindex required"),
        ("embed_down", "models are unavailable"),
        ("qdrant_down", "vector index is unavailable"),
    ],
)
async def test_failures_are_503_and_logged(setup: str, message: str) -> None:
    ml = FakeMl()
    store = FakeStore(hits("T0000000001:ru:a113:c0"), [])
    kwargs: dict[str, Any] = {"ml": ml, "store": store}
    if setup == "no_manifest":
        service, _, _ = make_service(**kwargs)
        service._manifest = FakeManifest(None)  # type: ignore[assignment]
    elif setup == "no_index":
        service, _, _ = make_service(**kwargs, active=ActiveIndex(None, None, None))
    elif setup == "incompatible":
        service, _, _ = make_service(**kwargs, active=ActiveIndex("c", "old-compat-id", "0.0.1"))
    elif setup == "embed_down":
        ml.fail_embed = True
        service, _, _ = make_service(**kwargs)
    else:
        store.fail = True
        service, _, _ = make_service(**kwargs)
    with pytest.raises(SearchError) as info:
        await service.search(SearchRequest(query=QUERY), SearchContext(session_hash="h"))
    error: APIError = info.value
    assert error.status_code == 503
    assert error.code == "upstream_unavailable"
    assert message in error.message
    assert info.value.log_values["error_code"] == "upstream_unavailable"
    assert info.value.log_values["session_hash"] == "h"


async def test_kazakh_auto_detection_filters_by_lang() -> None:
    store = FakeStore(hits("T0000000001:kk:a52:c0"), hits("T0000000001:kk:a52:c0"))
    service, _, _ = make_service(store=store)
    outcome = await service.search(
        SearchRequest(query="Еңбек шартын бұзу негіздері"), SearchContext()
    )
    assert outcome.response.lang == "kk"
    lang_condition = store.filters[0].must[0]
    assert lang_condition.key == "lang"
    assert lang_condition.match.value == "kk"
    assert outcome.response.results[0].lang == "kk"


async def test_log_values_shape() -> None:
    service, _, _ = make_service()
    ctx = SearchContext(session_hash="abc", client="web")
    outcome = await service.search(SearchRequest(query="  Задержка   ЗАРПЛАТЫ "), ctx)
    values = outcome.log_values
    assert values["query"] == "Задержка   ЗАРПЛАТЫ"
    assert values["query_norm"] == "задержка зарплаты"
    assert values["session_hash"] == "abc"
    assert values["client"] == "web"
    assert values["result_count"] == len(outcome.response.results)
    assert values["results"][0]["rank"] == 1
    assert {"article_id", "chunk_id", "score", "score_type", "title", "doc_short_title"} <= set(
        values["results"][0]
    )
    assert values["search_ms"] == outcome.response.timing_ms["total"]
    assert values["filters"]["in_force_only"] is True


async def test_stale_no_index_state_is_refreshed_once() -> None:
    service, _, _ = make_service()
    index = FakeIndex(
        ActiveIndex(None, None, None),
        after_refresh=ActiveIndex("legal_chunks__0.0.0-fake", "fake", "0.0.0-fake"),
    )
    service._index = index
    outcome = await service.search(SearchRequest(query=QUERY), SearchContext())
    assert outcome.response.results
    assert index.refreshes == 1


async def test_compatible_index_is_not_refreshed() -> None:
    service, _, _ = make_service()
    index = FakeIndex(ActiveIndex("legal_chunks__0.0.0-fake", "fake", "0.0.0-fake"))
    service._index = index
    await service.search(SearchRequest(query=QUERY), SearchContext())
    assert index.refreshes == 0
