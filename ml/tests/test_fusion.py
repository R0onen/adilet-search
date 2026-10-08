import json
from pathlib import Path
from typing import Any

import pytest

from adilet_ml.retrieval.fusion import apply_rerank, article_id_of, collapse, fuse, rrf


def ids(items: list[Any]) -> list[str]:
    return [item.article_id for item in items]


def test_article_id_of() -> None:
    assert article_id_of("K1500000414:ru:a113-1:c12") == "K1500000414:ru:a113-1"
    with pytest.raises(ValueError, match="not a chunk id"):
        article_id_of("K1500000414:ru:a113")


def test_rrf_and_collapse() -> None:
    chunks = rrf(
        ["K1:ru:a1:c1", "K1:ru:a2:c0", "K1:ru:a1:c0"],
        ["K1:ru:a1:c0", "K1:ru:a2:c0"],
        k=60,
        w_dense=1.0,
        w_sparse=1.0,
    )
    candidates = collapse(chunks)
    assert ids(candidates) == ["K1:ru:a1", "K1:ru:a2"]
    assert candidates[0].best_chunk_id == "K1:ru:a1:c0"


def test_modes_and_rerank() -> None:
    dense = ["K1:ru:a1:c0", "K1:ru:a2:c0", "K1:ru:a3:c0"]
    sparse = ["K1:ru:a4:c0"]
    assert ids(fuse("semantic", dense, sparse, k=60, w_dense=1.0, w_sparse=1.0)) == [
        "K1:ru:a1",
        "K1:ru:a2",
        "K1:ru:a3",
    ]
    assert ids(fuse("keyword", dense, sparse, k=60, w_dense=1.0, w_sparse=1.0)) == [
        "K1:ru:a4"
    ]
    candidates = fuse("semantic", dense, [], k=60, w_dense=1.0, w_sparse=1.0)
    out = apply_rerank(candidates, {"K1:ru:a2": 0.9, "K1:ru:a1": 0.1}, top_n=3)
    assert ids(out) == ["K1:ru:a2", "K1:ru:a1", "K1:ru:a3"]


@pytest.mark.parametrize(
    "case",
    json.loads((Path(__file__).parents[2] / "contracts/fixtures/fusion_cases.json").read_text())[
        "cases"
    ],
    ids=lambda c: c["name"],
)
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
    assert ids(candidates) == [item["article_id"] for item in case["expected"]]
    for got, want in zip(candidates, case["expected"], strict=True):
        if "best_chunk_id" in want:
            assert got.best_chunk_id == want["best_chunk_id"]
        if "score" in want:
            assert got.score == pytest.approx(want["score"])
