"""Evaluate a running backend API on the committed eval set."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

from adilet_ml.eval.metrics import Qrels, metric_bundle


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _qrels(path: Path) -> Qrels:
    qrels: Qrels = defaultdict(dict)
    for row in _read_jsonl(path):
        qrels[str(row["query_id"])][str(row["article_id"])] = int(row["relevance"])
    return dict(qrels)


def _search(
    client: httpx.Client,
    query: dict[str, Any],
    mode: str,
    top_k: int,
) -> tuple[list[str], float]:
    started = time.perf_counter()
    response = client.post(
        "/api/v1/search",
        json={
            "query": query["text"],
            "lang": query["lang"],
            "mode": mode,
            "top_k": top_k,
        },
    )
    response.raise_for_status()
    elapsed_ms = (time.perf_counter() - started) * 1000
    data = response.json()
    article_ids = [str(item["article_id"]) for item in data.get("results", [])]
    return article_ids, elapsed_ms


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--queries", type=Path, default=Path("data/eval/queries.jsonl"))
    parser.add_argument("--qrels", type=Path, default=Path("data/eval/qrels.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("docs/report/final_eval_api.json"))
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args(argv)

    queries = _read_jsonl(args.queries)
    qrels = _qrels(args.qrels)
    payload: dict[str, Any] = {"base_url": args.base_url, "modes": {}}
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=30.0) as client:
        for mode in ("hybrid", "semantic", "keyword"):
            run: dict[str, list[str]] = {}
            latencies: list[float] = []
            for query in queries:
                article_ids, elapsed_ms = _search(client, query, mode, args.top_k)
                run[str(query["query_id"])] = article_ids
                latencies.append(elapsed_ms)
            ordered = sorted(latencies)
            p50 = ordered[len(ordered) // 2] if ordered else 0.0
            p95 = ordered[min(len(ordered) - 1, round(len(ordered) * 0.95))] if ordered else 0.0
            payload["modes"][mode] = {
                **metric_bundle(qrels, run),
                "latency_ms_p50": p50,
                "latency_ms_p95": p95,
            }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
