"""Build the known-item evaluation set: every article's own title is a query for that article.

    python ml/scripts/build_title_eval.py [--data-dir data/processed] [--eval-dir data/eval]

There are no human relevance labels yet, so the labels come from the corpus itself. Two caveats,
to be repeated wherever these numbers are reported ("title-query (proxy) evaluation"):
- titles use the legislator's own words, so they favour lexical methods over real user questions;
- the product index embeds a header with the title in every chunk (`text_for_embedding`), so
  title queries are only a fair test against the article body (`text`). The baseline scripts
  search the body; through the product API this set is a sanity check, not a quality measure.
LLM-written plain-language questions (`build_synthetic_eval.py`) and a human gold set
(`data/eval/labeling/GUIDE.md`) are the stronger tests.

Writes `queries.jsonl`, `qrels.jsonl` and `splits.json`:
- one query per article with a usable title (at least 2 words; generic titles shared by 3 or more
  articles of the same language are dropped: several articles would be equally correct);
- the article is relevant (3); nothing else is labelled;
- the split is 70/15/15 by `doc_id:unit_key`, so the RU and KK versions of an article are always
  in the same subset, stratified by document, seed 42.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
MIN_WORDS = 2
GENERIC_FROM = 3
SPLIT = {"train": 0.70, "val": 0.15, "test": 0.15}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def usable_titles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        a
        for a in articles
        if a["unit_status"] == "in_force"
        and a["unit_title"]
        and len(a["unit_title"].split()) >= MIN_WORDS
    ]
    counts = Counter((a["lang"], a["unit_title"].strip().lower()) for a in rows)
    return [a for a in rows if counts[(a["lang"], a["unit_title"].strip().lower())] < GENERIC_FROM]


def split_groups(groups_by_doc: dict[str, list[str]], seed: int) -> dict[str, str]:
    """group -> split, stratified by document."""
    assignment: dict[str, str] = {}
    for doc_id in sorted(groups_by_doc):
        groups = sorted(groups_by_doc[doc_id])
        random.Random(f"{seed}:{doc_id}").shuffle(groups)  # noqa: S311 - reproducible split
        n_train = round(len(groups) * SPLIT["train"])
        n_val = round(len(groups) * SPLIT["val"])
        for index, group in enumerate(groups):
            split = "train" if index < n_train else "val" if index < n_train + n_val else "test"
            assignment[group] = split
    return assignment


def build(data_dir: Path, seed: int = 42) -> tuple[list[dict], list[dict], dict[str, Any]]:
    columns = ["article_id", "doc_id", "lang", "unit_key", "unit_title", "unit_status"]
    articles = pq.read_table(data_dir / "articles.parquet", columns=columns).to_pylist()
    rows = sorted(usable_titles(articles), key=lambda a: a["article_id"])

    groups_by_doc: dict[str, set[str]] = defaultdict(set)
    for a in rows:
        groups_by_doc[a["doc_id"]].add(f"{a['doc_id']}:{a['unit_key']}")
    assignment = split_groups({d: sorted(g) for d, g in groups_by_doc.items()}, seed)

    queries, qrels = [], []
    query_splits: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    for number, a in enumerate(rows, 1):
        query_id = f"t{number:05d}"
        queries.append(
            {
                "query_id": query_id,
                "text": a["unit_title"].strip(),
                "lang": a["lang"],
                "source": "title",
                "query_type": "known_item",
                "answerable": True,
            }
        )
        qrels.append({"query_id": query_id, "article_id": a["article_id"], "relevance": 3})
        query_splits[assignment[f"{a['doc_id']}:{a['unit_key']}"]].append(query_id)

    splits = {
        "version": "splits_v2_title",
        "seed": seed,
        "group_key": "doc_id:unit_key",
        "proportions": SPLIT,
        "query_splits": query_splits,
        "counts": {
            split: {
                "queries": len(ids),
                "ru": sum(queries[int(i[1:]) - 1]["lang"] == "ru" for i in ids),
                "kk": sum(queries[int(i[1:]) - 1]["lang"] == "kk" for i in ids),
            }
            for split, ids in query_splits.items()
        },
        "gold": {"val": [], "test": []},
        "notes": "Title-query (known-item) proxy labels; no human gold set yet.",
    }
    return queries, qrels, splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data/processed")
    parser.add_argument("--eval-dir", type=Path, default=REPO_ROOT / "data/eval")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    queries, qrels, splits = build(args.data_dir, args.seed)
    args.eval_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("queries.jsonl", queries), ("qrels.jsonl", qrels)):
        text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        (args.eval_dir / name).write_text(text, encoding="utf-8", newline="\n")
    splits["sha256"] = {
        name: _sha256(args.eval_dir / name) for name in ("queries.jsonl", "qrels.jsonl")
    }
    (args.eval_dir / "splits.json").write_text(
        json.dumps(splits, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {len(queries)} queries to {args.eval_dir}: {splits['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
