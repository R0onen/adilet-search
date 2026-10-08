import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).parents[2]
EVAL_DIR = ROOT / "data" / "eval"
DATA_DIR = ROOT / "data" / "sample"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_seed_splits_are_frozen_and_non_overlapping() -> None:
    splits = json.loads((EVAL_DIR / "splits.json").read_text(encoding="utf-8"))
    assert splits["sha256"]["queries.jsonl"] == hashlib.sha256(
        (EVAL_DIR / "queries.jsonl").read_bytes()
    ).hexdigest()
    assert splits["sha256"]["qrels.jsonl"] == hashlib.sha256(
        (EVAL_DIR / "qrels.jsonl").read_bytes()
    ).hexdigest()

    groups = [set(splits["synthetic"][name]) for name in ("train", "val", "test")]
    assert groups[0].isdisjoint(groups[1])
    assert groups[0].isdisjoint(groups[2])
    assert groups[1].isdisjoint(groups[2])


def test_synthetic_queries_follow_article_group_split() -> None:
    splits = json.loads((EVAL_DIR / "splits.json").read_text(encoding="utf-8"))
    articles = pq.read_table(DATA_DIR / "articles.parquet").to_pylist()
    article_groups = {
        row["article_id"]: f"{row['doc_id']}:{row['unit_key']}"
        for row in articles
    }
    group_to_split = {
        group: split
        for split, groups in splits["synthetic"].items()
        for group in groups
    }
    queries = {row["query_id"]: row for row in _read_jsonl(EVAL_DIR / "queries.jsonl")}
    qrels = _read_jsonl(EVAL_DIR / "qrels.jsonl")
    for row in qrels:
        if int(row["relevance"]) < 3:
            continue
        query = queries[row["query_id"]]
        if query["source"] != "synthetic":
            continue
        group = article_groups[row["article_id"]]
        query_split = next(
            split
            for split, ids in splits["synthetic_query_splits"].items()
            if row["query_id"] in ids
        )
        assert group_to_split[group] == query_split
