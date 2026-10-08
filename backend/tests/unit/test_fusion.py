"""services/fusion.py against contracts/ml_service.md §2.

The hand-written cases cover every rule. When ML publishes contracts/fixtures/fusion_cases.json,
`test_contract_fixture` runs it too (format proposed in docs/status/backend.md).
"""

import json
from typing import Any

import pytest

from app.services.fusion import Candidate, apply_rerank, article_id_of, collapse, fuse, rrf
from tests.conftest import CONTRACTS

A = "K1:ru:a1"
B = "K1:ru:a2"
C = "K1:ru:a3"


def ids(candidates: list[Candidate]) -> list[str]:
    return [c.article_id for c in candidates]


def test_article_id_of() -> None:
    assert article_id_of("K1500000414:ru:a113-1:c12") == "K1500000414:ru:a113-1"
    with pytest.raises(ValueError, match="not a chunk id"):
        article_id_of("K1500000414:ru:a113")


def test_rrf_formula() -> None:
    fused = rrf([f"{A}:c0", f"{B}:c0"], [f"{B}:c0"], k=60, w_dense=1.0, w_sparse=1.0)
    scores = {f.chunk_id: f.score for f in fused}
    assert scores[f"{B}:c0"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores[f"{A}:c0"] == pytest.approx(1 / 61)
    assert [f.chunk_id for f in fused] == [f"{B}:c0", f"{A}:c0"]


def test_unequal_weights() -> None:
    fused = rrf([f"{A}:c0"], [f"{B}:c0"], k=60, w_dense=0.5, w_sparse=2.0)
    assert [f.chunk_id for f in fused] == [f"{B}:c0", f"{A}:c0"]
    assert fused[0].score == pytest.approx(2.0 / 61)


def test_tie_prefers_chunk_with_a_dense_rank() -> None:
    # A is dense rank 2 only, B is sparse rank 2 only: equal F. B counts as worst dense rank.
    fused = rrf([f"{C}:c0", f"{A}:c0"], [f"{C}:c0", f"{B}:c0"], k=60, w_dense=1.0, w_sparse=1.0)
    assert fused[1].score == fused[2].score
    assert [f.chunk_id for f in fused] == [f"{C}:c0", f"{A}:c0", f"{B}:c0"]


def test_tie_prefers_lower_dense_rank_over_chunk_id() -> None:
    # w_dense = 0 makes every F equal; B has the better dense rank although "A" < "B".
    fused = rrf([f"{B}:c0", f"{A}:c0"], [], k=60, w_dense=0.0, w_sparse=1.0)
    assert [f.chunk_id for f in fused] == [f"{B}:c0", f"{A}:c0"]


def test_tie_without_dense_rank_uses_chunk_id() -> None:
    fused = rrf([], [f"{B}:c0", f"{A}:c0"], k=60, w_dense=1.0, w_sparse=0.0)
    assert [f.chunk_id for f in fused] == [f"{A}:c0", f"{B}:c0"]


def test_duplicates_keep_first_rank_and_limits_truncate() -> None:
    fused = rrf(
        [f"{A}:c0", f"{A}:c0", f"{B}:c0", f"{C}:c0"],
        [],
        k=60,
        w_dense=1.0,
        w_sparse=1.0,
        dense_limit=3,
    )
    assert {f.chunk_id: f.dense_rank for f in fused} == {f"{A}:c0": 1, f"{B}:c0": 2}


def test_collapse_keeps_best_chunk_per_article() -> None:
    fused = rrf(
        [f"{A}:c1", f"{B}:c0", f"{A}:c0"],
        [f"{A}:c0", f"{B}:c0"],
        k=60,
        w_dense=1.0,
        w_sparse=1.0,
    )
    candidates = collapse(fused)
    assert ids(candidates) == [A, B]
    # A:c0 (dense 3, sparse 1) beats A:c1 (dense 1 only).
    assert candidates[0].best_chunk_id == f"{A}:c0"
    assert candidates[0].fusion_score == pytest.approx(1 / 63 + 1 / 61)


def test_modes() -> None:
    dense = [f"{A}:c0"]
    sparse = [f"{B}:c0"]
    kwargs: dict[str, Any] = {"k": 60, "w_dense": 1.0, "w_sparse": 1.0}
    assert ids(fuse("hybrid", dense, sparse, **kwargs)) == [A, B]
    assert ids(fuse("semantic", dense, sparse, **kwargs)) == [A]
    assert ids(fuse("keyword", dense, sparse, **kwargs)) == [B]


def test_empty_lists() -> None:
    assert fuse("hybrid", [], [], k=60, w_dense=1.0, w_sparse=1.0) == []


def test_rerank_reorders_head_only_and_is_stable() -> None:
    candidates = [
        Candidate(x, f"{x}:c0", 1.0 / (i + 1)) for i, x in enumerate([A, B, C, "K1:ru:a4"])
    ]
    out = apply_rerank(candidates, {A: 0.1, B: 0.9, C: 0.1}, top_n=3)
    assert ids(out) == [B, A, C, "K1:ru:a4"]  # A before C: tie keeps the fused order
    assert out[0].rerank_score == 0.9
    assert out[0].score == 0.9
    assert out[3].rerank_score is None
    assert out[3].score == out[3].fusion_score


def test_rerank_missing_score_goes_last_in_head() -> None:
    candidates = [Candidate(x, f"{x}:c0", 1.0) for x in (A, B, C)]
    out = apply_rerank(candidates, {B: 0.2, C: 0.5}, top_n=3)
    assert ids(out) == [C, B, A]


# --- contracts/fixtures/fusion_cases.json (ML-owned) ----------------------------------------

FIXTURE = CONTRACTS / "fixtures" / "fusion_cases.json"


def _fixture_cases() -> list[dict[str, Any]]:
    if not FIXTURE.exists():
        return []
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = data["cases"] if isinstance(data, dict) else data
    return cases


@pytest.mark.skipif(not FIXTURE.exists(), reason="ML has not published fusion_cases.json yet")
@pytest.mark.parametrize("case", _fixture_cases(), ids=lambda c: str(c.get("name")))
def test_contract_fixture(case: dict[str, Any]) -> None:
    params = case["params"]
    candidates = fuse(
        case.get("mode", "hybrid"),
        case.get("dense", []),
        case.get("sparse", []),
        k=params["rrf_k"],
        w_dense=params["weights"]["dense"],
        w_sparse=params["weights"]["sparse"],
        dense_limit=params.get("dense_limit"),
        sparse_limit=params.get("sparse_limit"),
    )
    if "rerank_scores" in case:
        candidates = apply_rerank(candidates, case["rerank_scores"], params["rerank_top_n"])
    expected = case["expected"]
    assert ids(candidates) == [e["article_id"] for e in expected]
    for got, want in zip(candidates, expected, strict=True):
        if "best_chunk_id" in want:
            assert got.best_chunk_id == want["best_chunk_id"]
        if "score" in want:
            assert got.score == pytest.approx(want["score"], rel=1e-9)
