"""The search pipeline (contracts/api.md `/search`, contracts/ml_service.md §2).

validate → detect language → embed (only the vectors the mode needs) → dense + sparse retrieval in
parallel → weighted RRF + collapse to articles → rerank the head → assemble top-k from Postgres.

Every stage has a time budget. A reranker failure or timeout degrades to the fused order
(`degraded: ["rerank"]`). An embed/retrieval failure or an incompatible index currently answers
503 `upstream_unavailable`; the Postgres full-text fallback replaces that in BE-04.
"""

import asyncio
import time
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

import structlog

from app.core.errors import APIError
from app.db.models import Article, Document
from app.schemas.common import Highlight, SearchResult
from app.schemas.ml import EmbedResponse, Manifest, RerankCandidate, RerankResponse
from app.schemas.search import SearchRequest, SearchResponse, SearchTiming
from app.services.fusion import Candidate, apply_rerank, fuse
from app.services.index_info import ActiveIndex
from app.services.lang import resolve_lang
from app.services.mappers import article_ref, document_ref
from app.services.ml_client import MlUnavailable
from app.services.qdrant_store import Hit, SearchFilter, build_filter
from app.services.query_log import normalise_query
from app.services.snippets import highlights, make_snippet

log = structlog.get_logger(__name__)

T = TypeVar("T")
# Extra candidates fetched from Postgres in case some ids are missing there (e.g. mid-reindex).
ASSEMBLE_SLACK = 10


class Embedder(Protocol):
    async def embed(
        self,
        texts: list[str],
        kind: Literal["query", "passage"],
        *,
        dense: bool = True,
        sparse: bool = True,
        timeout_s: float | None = None,
    ) -> EmbedResponse: ...

    async def rerank(
        self, query: str, candidates: list[RerankCandidate], *, timeout_s: float | None = None
    ) -> RerankResponse: ...


class VectorSearch(Protocol):
    async def search_dense(
        self, vector: list[float], query_filter: Any, limit: int
    ) -> list[Hit]: ...

    async def search_sparse(
        self, indices: list[int], values: list[float], query_filter: Any, limit: int
    ) -> list[Hit]: ...


class ArticleLookup(Protocol):
    async def __call__(self, article_ids: list[str]) -> dict[str, tuple[Article, Document]]: ...


class ManifestSource(Protocol):
    async def get(self) -> Manifest | None: ...


class IndexSource(Protocol):
    async def get(self) -> ActiveIndex: ...


@dataclass(frozen=True)
class SearchBudgets:
    embed_s: float = 2.0
    retrieve_s: float = 2.0
    rerank_s: float = 1.5


@dataclass
class SearchContext:
    session_hash: str | None = None
    client: str = "unknown"
    ua_family: str | None = None
    endpoint: str = "search"


@dataclass
class AssembledResult:
    """A result with its ORM rows, so /answer can reuse them without another query."""

    result: SearchResult
    article: Article
    document: Document
    chunk_text: str


@dataclass
class SearchOutcome:
    response: SearchResponse
    items: list[AssembledResult]
    log_values: dict[str, Any] = field(default_factory=dict)


class SearchError(APIError):
    """An APIError that still carries the query-log row for the failed request."""

    def __init__(self, error: APIError, log_values: dict[str, Any]) -> None:
        super().__init__(error.status_code, error.message, error.code, error.details, error.headers)
        self.log_values = log_values


def _ms(seconds: float) -> int:
    return round(seconds * 1000)


def _unavailable(message: str) -> APIError:
    return APIError(503, message, code="upstream_unavailable")


class SearchService:
    def __init__(
        self,
        ml: Embedder,
        store: VectorSearch,
        lookup: ArticleLookup,
        manifest: ManifestSource,
        index: IndexSource,
        budgets: SearchBudgets,
    ) -> None:
        self._ml = ml
        self._store = store
        self._lookup = lookup
        self._manifest = manifest
        self._index = index
        self._budgets = budgets

    async def search(self, request: SearchRequest, ctx: SearchContext) -> SearchOutcome:
        started = time.perf_counter()
        query_id = uuid.uuid4()
        lang = resolve_lang(request.lang, request.query)
        log_values: dict[str, Any] = {
            "query_id": query_id,
            "session_hash": ctx.session_hash,
            "client": ctx.client,
            "ua_family": ctx.ua_family,
            "endpoint": ctx.endpoint,
            "query": request.query,
            "query_norm": normalise_query(request.query),
            "lang": lang,
            "mode": request.mode,
            "filters": request.filters.model_dump(mode="json"),
            "top_k": request.top_k,
        }
        try:
            outcome = await self._run(request, query_id, lang, started)
        except APIError as exc:
            log_values.update(
                error_code=exc.code,
                search_ms=_ms(time.perf_counter() - started),
                timing_ms={"total": _ms(time.perf_counter() - started)},
            )
            raise SearchError(exc, log_values) from exc
        response = outcome.response
        log_values.update(
            result_count=len(response.results),
            zero_results=not response.results,
            top_article_id=response.results[0].article.article_id if response.results else None,
            total_candidates=response.total_candidates,
            results=[
                {
                    "rank": item.result.rank,
                    "article_id": item.result.article.article_id,
                    "chunk_id": item.result.chunk_id,
                    "score": item.result.score,
                    "score_type": item.result.score_type,
                    "title": item.article.unit_title,
                    "doc_short_title": item.document.short_title,
                }
                for item in outcome.items
            ],
            timing_ms=dict(response.timing_ms),
            search_ms=response.timing_ms.get("total"),
            degraded=list(response.degraded),
            pipeline_version=response.pipeline_version,
        )
        outcome.log_values = log_values
        return outcome

    async def _timed(self, awaitable: Awaitable[T], budget_s: float) -> T:
        return await asyncio.wait_for(awaitable, budget_s)

    async def _run(
        self, request: SearchRequest, query_id: uuid.UUID, lang: Literal["ru", "kk"], started: float
    ) -> SearchOutcome:
        manifest = await self._manifest.get()
        if manifest is None:
            raise _unavailable("Search models are not available (model manifest not loaded)")
        try:
            active = await self._timed(self._index.get(), self._budgets.retrieve_s)
        except Exception as exc:
            log.warning("index_info_failed", error=type(exc).__name__)
            raise _unavailable("The search index is unavailable") from exc
        if active.collection is None:
            raise _unavailable("No search index has been built yet")
        if not active.compatible_with(manifest.index_compat_id):
            log.warning(
                "index_incompatible",
                collection=active.collection,
                index_compat_id=active.index_compat_id,
                manifest_index_compat_id=manifest.index_compat_id,
            )
            raise _unavailable("The search index is incompatible with the models: reindex required")

        params = manifest.retrieval
        mode = request.mode
        need_dense = mode != "keyword"
        need_sparse = mode != "semantic"
        timing: SearchTiming = {}

        # 1. embed
        t = time.perf_counter()
        try:
            embedded = await self._ml.embed(
                [request.query],
                "query",
                dense=need_dense,
                sparse=need_sparse,
                timeout_s=self._budgets.embed_s,
            )
        except MlUnavailable as exc:
            log.warning("embed_failed", error=str(exc))
            raise _unavailable("The search models are unavailable") from exc
        timing["embed"] = _ms(time.perf_counter() - t)

        # 2. retrieve (dense and sparse in parallel)
        t = time.perf_counter()
        query_filter = build_filter(
            SearchFilter(
                lang=lang,
                doc_ids=request.filters.doc_ids,
                doc_types=request.filters.doc_types,
                in_force_only=request.filters.in_force_only,
                date_from=request.filters.date_from,
                date_to=request.filters.date_to,
            )
        )

        async def no_hits() -> list[Hit]:
            return []

        dense_call = (
            self._store.search_dense(embedded.dense[0], query_filter, params.dense_limit)
            if need_dense and embedded.dense
            else no_hits()
        )
        sparse_call = (
            self._store.search_sparse(
                embedded.sparse[0].indices,
                embedded.sparse[0].values,
                query_filter,
                params.sparse_limit,
            )
            if need_sparse and embedded.sparse
            else no_hits()
        )
        try:
            dense_hits, sparse_hits = await self._timed(
                asyncio.gather(dense_call, sparse_call), self._budgets.retrieve_s
            )
        except Exception as exc:
            log.warning("retrieve_failed", error=type(exc).__name__)
            raise _unavailable("The vector index is unavailable") from exc
        timing["retrieve"] = _ms(time.perf_counter() - t)

        # 3. fuse + collapse
        t = time.perf_counter()
        payloads = {hit.chunk_id: hit.payload for hit in (*dense_hits, *sparse_hits)}
        candidates = fuse(
            mode,
            [h.chunk_id for h in dense_hits],
            [h.chunk_id for h in sparse_hits],
            k=params.rrf_k,
            w_dense=params.weights.get("dense", 1.0),
            w_sparse=params.weights.get("sparse", 1.0),
            dense_limit=params.dense_limit,
            sparse_limit=params.sparse_limit,
        )
        timing["fuse"] = _ms(time.perf_counter() - t)

        # 4. rerank the head (not in keyword mode)
        degraded: list[Literal["rerank", "semantic", "generation"]] = []
        if mode != "keyword" and candidates:
            t = time.perf_counter()
            head = candidates[: params.rerank_top_n]
            try:
                reranked = await self._ml.rerank(
                    request.query,
                    [
                        RerankCandidate(
                            id=c.article_id,
                            text=str(payloads[c.best_chunk_id].get("text_for_embedding", "")),
                        )
                        for c in head
                    ],
                    timeout_s=self._budgets.rerank_s,
                )
                scores = {r.id: r.score for r in reranked.results}
                candidates = apply_rerank(candidates, scores, params.rerank_top_n)
            except MlUnavailable as exc:
                log.warning("rerank_degraded", error=str(exc))
                degraded.append("rerank")
            timing["rerank"] = _ms(time.perf_counter() - t)

        # 5. assemble
        items = await self._assemble(request, candidates, payloads)
        timing["total"] = _ms(time.perf_counter() - started)
        response = SearchResponse(
            query_id=query_id,
            query=request.query,
            lang=lang,
            mode=mode,
            results=[item.result for item in items],
            total_candidates=len(candidates),
            degraded=degraded,
            timing_ms=timing,
            pipeline_version=manifest.pipeline_version,
        )
        return SearchOutcome(response=response, items=items)

    async def _assemble(
        self,
        request: SearchRequest,
        candidates: list[Candidate],
        payloads: dict[str, dict[str, Any]],
    ) -> list[AssembledResult]:
        wanted = candidates[: request.top_k + ASSEMBLE_SLACK]
        try:
            rows = await self._lookup([c.article_id for c in wanted])
        except Exception as exc:
            log.warning("assemble_failed", error=type(exc).__name__)
            raise _unavailable("The database is unavailable") from exc
        items: list[AssembledResult] = []
        for candidate in wanted:
            if len(items) == request.top_k:
                break
            row = rows.get(candidate.article_id)
            if row is None:
                log.warning("article_missing_in_db", article_id=candidate.article_id)
                continue
            article, document = row
            chunk_text = str(payloads[candidate.best_chunk_id].get("text", ""))
            snippet = make_snippet(chunk_text, request.query)
            result = SearchResult(
                rank=len(items) + 1,
                article=article_ref(article),
                doc=document_ref(document),
                chunk_id=candidate.best_chunk_id,
                lang=article.lang,
                score=round(candidate.score, 6),
                score_type="rerank" if candidate.rerank_score is not None else "fusion",
                snippet=snippet,
                highlights=[
                    Highlight(start=s.start, end=s.end) for s in highlights(snippet, request.query)
                ],
            )
            items.append(AssembledResult(result, article, document, chunk_text))
        return items
