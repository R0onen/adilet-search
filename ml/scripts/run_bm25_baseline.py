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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/sample"))
    parser.add_argument("--queries", type=Path, default=Path("data/eval/queries.jsonl"))
    parser.add_argument("--qrels", type=Path, default=Path("data/eval/qrels.jsonl"))
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--run-dir", type=Path, default=Path("ml/experiments/20261008_bm25_seed"))
    args = parser.parse_args(argv)

    chunks = pq.read_table(args.data_dir / "chunks.parquet").to_pylist()
    queries = _read_jsonl(args.queries)
    qrels_rows = _read_jsonl(args.qrels)
    by_lang: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for chunk in chunks:
        by_lang[str(chunk["lang"])].append(
            (str(chunk["article_id"]), str(chunk["text_for_embedding"]))
        )
    indexes = {lang: BM25Index().fit(docs, lang) for lang, docs in by_lang.items()}
    run: dict[str, list[str]] = {}
    for query in queries:
        lang = str(query["lang"])
        hits = indexes[lang].search(str(query["text"]), args.top_k, lang)
        seen: set[str] = set()
        ranked = []
        for hit in hits:
            if hit.doc_id in seen:
                continue
            seen.add(hit.doc_id)
            ranked.append(hit.doc_id)
        run[str(query["query_id"])] = ranked
    qrels: Qrels = defaultdict(dict)
    for row in qrels_rows:
        qrels[str(row["query_id"])][str(row["article_id"])] = int(row["relevance"])
    metrics = {
        "model": "bm25_seed",
        "queries": len(queries),
        **metric_bundle(dict(qrels), run),
    }
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.run_dir / "config.yaml").write_text(
        "\n".join(
            [
                "model: bm25_seed",
                f"data_dir: {args.data_dir.as_posix()}",
                f"queries: {args.queries.as_posix()}",
                f"qrels: {args.qrels.as_posix()}",
                f"top_k: {args.top_k}",
                "k1: 1.2",
                "b: 0.75",
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
