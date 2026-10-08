"""Run the offline hash-dense retrieval baseline used by the bootstrap service."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from adilet_ml.eval.metrics import Qrels, metric_bundle
from adilet_ml.serving.engine import HashEmbedder


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/sample"))
    parser.add_argument("--queries", type=Path, default=Path("data/eval/queries.jsonl"))
    parser.add_argument("--qrels", type=Path, default=Path("data/eval/qrels.jsonl"))
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("ml/experiments/20261008_hash_dense_seed"),
    )
    args = parser.parse_args(argv)

    queries = _read_jsonl(args.queries)
    qrels_rows = _read_jsonl(args.qrels)
    articles = pq.read_table(args.data_dir / "articles.parquet").to_pylist()
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for article in articles:
        by_lang[str(article["lang"])].append(article)

    embedder = HashEmbedder(dim=768, max_seq_len=512)
    article_vectors: dict[str, list[tuple[str, np.ndarray]]] = {}
    for lang, rows in by_lang.items():
        dense, _ = embedder.encode([str(row["text"]) for row in rows], ["passage: "] * len(rows))
        article_vectors[lang] = [
            (str(row["article_id"]), np.array(vector, dtype=np.float32))
            for row, vector in zip(rows, dense, strict=True)
        ]

    run: dict[str, list[str]] = {}
    for query in queries:
        lang = str(query["lang"])
        dense, _ = embedder.encode([str(query["text"])], ["query: "])
        q_vec = np.array(dense[0], dtype=np.float32)
        scored = [
            (article_id, float(np.dot(q_vec, article_vec)))
            for article_id, article_vec in article_vectors[lang]
        ]
        run[str(query["query_id"])] = [
            article_id for article_id, _ in sorted(scored, key=lambda item: (-item[1], item[0]))
        ]

    qrels: Qrels = defaultdict(dict)
    for row in qrels_rows:
        qrels[str(row["query_id"])][str(row["article_id"])] = int(row["relevance"])
    metrics = {
        "model": "hash_dense_seed",
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
                "model: hash_dense_seed",
                "dim: 768",
                "query_prefix: 'query: '",
                "passage_prefix: 'passage: '",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (args.run_dir / "env.json").write_text(
        json.dumps(
            {
                "python": sys.version,
                "platform": platform.platform(),
                "numpy": np.__version__,
            },
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
