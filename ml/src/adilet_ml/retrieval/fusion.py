"""Weighted RRF fusion from `contracts/ml_service.md` section 2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FusedChunk:
    chunk_id: str
    score: float
    dense_rank: int | None = None
    sparse_rank: int | None = None


@dataclass
class Candidate:
    article_id: str
    best_chunk_id: str
    fusion_score: float
    rerank_score: float | None = None

    @property
    def score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else self.fusion_score


def article_id_of(chunk_id: str) -> str:
    if ":c" not in chunk_id:
        raise ValueError(f"{chunk_id!r} is not a chunk id")
    return chunk_id.rsplit(":c", 1)[0]


def _rank_map(ids: list[str], limit: int | None) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for chunk_id in ids[:limit]:
        if chunk_id not in ranks:
            ranks[chunk_id] = len(ranks) + 1
    return ranks


def rrf(
    dense: list[str],
    sparse: list[str],
    *,
    k: int,
    w_dense: float,
    w_sparse: float,
    dense_limit: int | None = None,
    sparse_limit: int | None = None,
) -> list[FusedChunk]:
    dense_ranks = _rank_map(dense, dense_limit)
    sparse_ranks = _rank_map(sparse, sparse_limit)
    chunk_ids = set(dense_ranks) | set(sparse_ranks)
    fused = []
    for chunk_id in chunk_ids:
        score = 0.0
        if chunk_id in dense_ranks:
            score += w_dense / (k + dense_ranks[chunk_id])
        if chunk_id in sparse_ranks:
            score += w_sparse / (k + sparse_ranks[chunk_id])
        fused.append(
            FusedChunk(
                chunk_id=chunk_id,
                score=score,
                dense_rank=dense_ranks.get(chunk_id),
                sparse_rank=sparse_ranks.get(chunk_id),
            )
        )
    return sorted(
        fused,
        key=lambda item: (
            -item.score,
            item.dense_rank if item.dense_rank is not None else 10**12,
            item.chunk_id,
        ),
    )


def collapse(chunks: list[FusedChunk]) -> list[Candidate]:
    """Collapse sorted chunks to articles, keeping the best chunk per article."""
    best: dict[str, Candidate] = {}
    order: list[str] = []
    for chunk in chunks:
        article_id = article_id_of(chunk.chunk_id)
        if article_id not in best:
            best[article_id] = Candidate(article_id, chunk.chunk_id, chunk.score)
            order.append(article_id)
            continue
        current = best[article_id]
        if chunk.score > current.fusion_score:
            current.best_chunk_id = chunk.chunk_id
            current.fusion_score = chunk.score
    return [best[article_id] for article_id in order]


def fuse(
    mode: str,
    dense: list[str],
    sparse: list[str],
    *,
    k: int,
    w_dense: float,
    w_sparse: float,
    dense_limit: int | None = None,
    sparse_limit: int | None = None,
) -> list[Candidate]:
    if mode == "semantic":
        sparse = []
    elif mode == "keyword":
        dense = []
    elif mode != "hybrid":
        raise ValueError(f"unknown fusion mode {mode!r}")
    return collapse(
        rrf(
            dense,
            sparse,
            k=k,
            w_dense=w_dense,
            w_sparse=w_sparse,
            dense_limit=dense_limit,
            sparse_limit=sparse_limit,
        )
    )


def apply_rerank(
    candidates: list[Candidate], rerank_scores: dict[str, float], top_n: int | None
) -> list[Candidate]:
    if top_n is None:
        top_n = len(candidates)
    head = candidates[:top_n]
    tail = candidates[top_n:]
    original_pos = {candidate.article_id: pos for pos, candidate in enumerate(head)}
    for candidate in head:
        candidate.rerank_score = rerank_scores.get(candidate.article_id)
    head.sort(
        key=lambda candidate: (
            candidate.rerank_score is None,
            -(candidate.rerank_score if candidate.rerank_score is not None else float("-inf")),
            original_pos[candidate.article_id],
        )
    )
    return head + tail
