"""Run a BM25 retrieval baseline on contract-shaped Parquet plus qrels JSONL."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from adilet_ml.eval.metrics import Qrels, metric_bundle
from adilet_ml.retrieval.bm25 import BM25Index


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data/processed")
    parser.add_argument("--eval-dir", type=Path, default=REPO_ROOT / "data/eval")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--k1", type=float, default=1.2)
    parser.add_argument("--b", type=float, default=0.75)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    # Article bodies only: `text_for_embedding` starts with a header that contains the title, and
    # the queries of the title eval set are the titles (see build_title_eval.py).
    columns = ["article_id", "lang", "chunk_index", "text"]
    chunks = pq.read_table(args.data_dir / "chunks.parquet", columns=columns).to_pylist()
    bodies: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    for chunk in chunks:
        bodies[(chunk["lang"], chunk["article_id"])].append((chunk["chunk_index"], chunk["text"]))
    by_lang: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for (lang, article_id), parts in sorted(bodies.items()):
        by_lang[lang].append((article_id, "\n".join(text for _, text in sorted(parts))))
    indexes = {
        lang: BM25Index(k1=args.k1, b=args.b).fit(docs, lang) for lang, docs in by_lang.items()
    }

    splits = json.loads((args.eval_dir / "splits.json").read_text(encoding="utf-8"))
    wanted = set(splits["query_splits"][args.split])
    queries = [q for q in _read_jsonl(args.eval_dir / "queries.jsonl") if q["query_id"] in wanted]
    qrels: Qrels = defaultdict(dict)
    for row in _read_jsonl(args.eval_dir / "qrels.jsonl"):
        if row["query_id"] in wanted:
            qrels[str(row["query_id"])][str(row["article_id"])] = int(row["relevance"])

    run: dict[str, list[str]] = {}
    for query in queries:
        lang = str(query["lang"])
        hits = indexes[lang].search(str(query["text"]), args.top_k, lang)
        run[str(query["query_id"])] = [hit.doc_id for hit in hits]

    def bundle(lang: str | None) -> dict[str, float]:
        ids = [str(q["query_id"]) for q in queries if lang is None or q["lang"] == lang]
        return metric_bundle({i: qrels[i] for i in ids}, {i: run[i] for i in ids})

    metrics = {
        "model": "bm25_snowball",
        "eval": f"title-query (proxy), {args.split} split, article bodies",
        "queries": len(queries),
        **bundle(None),
        **{
            f"{lang}_{name}": value for lang in ("ru", "kk") for name, value in bundle(lang).items()
        },
    }
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.run_dir / "config.yaml").write_text(
        "\n".join(
            [
                "model: bm25_snowball",
                "tokenizer: lowercase + stopwords; Russian Snowball stemming; Kazakh unstemmed",
                "data_dir: data/processed (AdiletCodex v1.0, Tier-1, corpus_version 2026.09.17)",
                f"split: {args.split} (data/eval/splits.json, {splits['version']})",
                f"top_k: {args.top_k}",
                f"k1: {args.k1}",
                f"b: {args.b}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (args.run_dir / "env.json").write_text(
        json.dumps(
            {"python": sys.version, "platform": platform.platform()},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
