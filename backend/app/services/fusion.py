"""Fusion and candidate selection, exactly as contracts/ml_service.md §2 (normative).

1. Each retriever returns chunk ids ranked 1-based, truncated to its limit.
2. F(c) = sum over the lists that contain c of  w_s / (k + rank_s(c)).
3. Sort by F desc; ties: better (lower) dense rank first, chunks missing from the dense list
   count as worst; then chunk_id ascending.
4. Collapse to articles: score = max F over its chunks, best chunk = the argmax; keep step-3 order.
5. Rerank the first `rerank_top_n` articles; final order = reranker score desc, ties keep the
   fused order; the remaining articles follow in fused order.
6. Modes: `semantic` = dense list only; `keyword` = sparse list only and no rerank.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

Mode = Literal["hybrid", "semantic", "keyword"]


def article_id_of(chunk_id: str) -> str:
    """`{article_id}:c{n}` -> `{article_id}` (data_schema.md §2)."""
    article_id, sep, index = chunk_id.rpartition(":c")
    if not sep or not index.isdigit():
        raise ValueError(f"not a chunk id: {chunk_id!r}")
    return article_id


@dataclass(frozen=True, slots=True)
class FusedChunk:
    chunk_id: str
    score: float
    dense_rank: int | None
    sparse_rank: int | None


@dataclass(frozen=True, slots=True)
class Candidate:
    """One article after collapse (step 4), possibly reranked (step 5)."""

    article_id: str
    best_chunk_id: str
    fusion_score: float
    rerank_score: float | None = None

    @property
    def score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else self.fusion_score


def _ranks(ids: Sequence[str], limit: int | None) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for chunk_id in ids[:limit] if limit is not None else ids:
        if chunk_id not in ranks:  # a duplicate keeps its first (best) rank
            ranks[chunk_id] = len(ranks) + 1
    return ranks


def rrf(
    dense: Sequence[str],
    sparse: Sequence[str],
    *,
    k: float,
    w_dense: float,
    w_sparse: float,
    dense_limit: int | None = None,
    sparse_limit: int | None = None,
) -> list[FusedChunk]:
    """Steps 1–3: weighted reciprocal rank fusion of two ranked chunk lists."""
    dense_ranks = _ranks(dense, dense_limit)
    sparse_ranks = _ranks(sparse, sparse_limit)
    fused = []
    for chunk_id in dense_ranks.keys() | sparse_ranks.keys():
        d = dense_ranks.get(chunk_id)
        s = sparse_ranks.get(chunk_id)
        score = (w_dense / (k + d) if d is not None else 0.0) + (
            w_sparse / (k + s) if s is not None else 0.0
        )
        fused.append(FusedChunk(chunk_id, score, d, s))
    fused.sort(
        key=lambda c: (
            -c.score,
            c.dense_rank if c.dense_rank is not None else math.inf,
            c.chunk_id,
        )
    )
    return fused


def collapse(fused: Sequence[FusedChunk]) -> list[Candidate]:
    """Step 4: one candidate per article, in the order of its best chunk."""
    seen: set[str] = set()
    candidates = []
    for chunk in fused:  # already sorted: the first chunk of an article is its argmax
        article_id = article_id_of(chunk.chunk_id)
        if article_id not in seen:
            seen.add(article_id)
            candidates.append(Candidate(article_id, chunk.chunk_id, chunk.score))
    return candidates


def fuse(
    mode: Mode,
    dense: Sequence[str],
    sparse: Sequence[str],
    *,
    k: float,
    w_dense: float,
    w_sparse: float,
    dense_limit: int | None = None,
    sparse_limit: int | None = None,
) -> list[Candidate]:
    """Steps 1–4 for a mode (step 6): the article candidates in fused order."""
    if mode == "semantic":
        sparse = []
    elif mode == "keyword":
        dense = []
    fused = rrf(
        dense,
        sparse,
        k=k,
        w_dense=w_dense,
        w_sparse=w_sparse,
        dense_limit=dense_limit,
        sparse_limit=sparse_limit,
    )
    return collapse(fused)


def apply_rerank(
    candidates: Sequence[Candidate], scores: Mapping[str, float], top_n: int
) -> list[Candidate]:
    """Step 5: reorder the first `top_n` candidates by reranker score (stable on ties).

    `scores` maps article_id -> reranker score for the reranked head. Head candidates without a
    score (should not happen) sort after the scored ones, in fused order.
    """
    head = [
        Candidate(c.article_id, c.best_chunk_id, c.fusion_score, scores.get(c.article_id))
        for c in candidates[:top_n]
    ]
    # sorted() is stable, so equal scores keep the fused order.
    head.sort(key=lambda c: -c.rerank_score if c.rerank_score is not None else math.inf)
    return head + list(candidates[top_n:])
