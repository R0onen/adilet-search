"""Create deterministic seed eval splits from qrels and sample corpus metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _article_groups(data_dir: Path) -> dict[str, str]:
    rows = pq.read_table(data_dir / "articles.parquet").to_pylist()
    return {
        str(row["article_id"]): f"{row['doc_id']}:{row['unit_key']}"
        for row in rows
    }


def _best_positive_groups(
    qrels: list[dict[str, Any]], article_groups: dict[str, str]
) -> dict[str, str]:
    by_query: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for row in qrels:
        rel = int(row["relevance"])
        if rel <= 0:
            continue
        article_id = str(row["article_id"])
        if article_id in article_groups:
            by_query[str(row["query_id"])].append((rel, article_groups[article_id]))
    return {
        query_id: sorted(items, key=lambda item: (-item[0], item[1]))[0][1]
        for query_id, items in by_query.items()
    }


def _split_groups(groups: list[str], seed: int) -> dict[str, list[str]]:
    shuffled = sorted(groups)
    random.Random(seed).shuffle(shuffled)  # noqa: S311 - deterministic split, not security.
    if len(shuffled) < 3:
        return {"train": shuffled, "val": [], "test": []}
    n_test = max(1, round(len(shuffled) * 0.1))
    n_val = max(1, round(len(shuffled) * 0.1))
    n_train = max(1, len(shuffled) - n_val - n_test)
    return {
        "train": sorted(shuffled[:n_train]),
        "val": sorted(shuffled[n_train : n_train + n_val]),
        "test": sorted(shuffled[n_train + n_val :]),
    }


def build_splits(data_dir: Path, eval_dir: Path, seed: int = 42) -> dict[str, Any]:
    queries = _read_jsonl(eval_dir / "queries.jsonl")
    qrels = _read_jsonl(eval_dir / "qrels.jsonl")
    article_groups = _article_groups(data_dir)
    query_group = _best_positive_groups(qrels, article_groups)

    synthetic_queries = [row for row in queries if row["source"] == "synthetic"]
    gold_queries = [row for row in queries if row["source"] == "gold"]
    synthetic_groups = _split_groups(sorted(set(query_group.values())), seed)

    query_splits: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    group_to_split = {
        group: split
        for split, groups in synthetic_groups.items()
        for group in groups
    }
    for row in synthetic_queries:
        query_id = str(row["query_id"])
        split = group_to_split.get(query_group.get(query_id), "test")
        query_splits[split].append(query_id)

    gold_ids = sorted(str(row["query_id"]) for row in gold_queries)
    gold_val_count = round(len(gold_ids) * 0.3)
    gold = {"val": gold_ids[:gold_val_count], "test": gold_ids[gold_val_count:]}

    return {
        "version": "splits_v1_seed",
        "seed": seed,
        "group_key": "doc_id:unit_key",
        "synthetic": synthetic_groups,
        "synthetic_query_splits": {key: sorted(value) for key, value in query_splits.items()},
        "gold": gold,
        "query_group": query_group,
        "sha256": {
            "queries.jsonl": _sha256(eval_dir / "queries.jsonl"),
            "qrels.jsonl": _sha256(eval_dir / "qrels.jsonl"),
        },
        "notes": (
            "Seed split for local baseline wiring; replace after human-labelled gold data exists."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/sample"))
    parser.add_argument("--eval-dir", type=Path, default=Path("data/eval"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    splits = build_splits(args.data_dir, args.eval_dir, args.seed)
    out = args.eval_dir / "splits.json"
    out.write_text(json.dumps(splits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
