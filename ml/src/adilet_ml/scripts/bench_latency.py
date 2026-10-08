"""Small latency benchmark for the running ML service."""

from __future__ import annotations

import argparse
import statistics
import time
from typing import Any

import httpx


def _post(client: httpx.Client, path: str, payload: dict[str, Any]) -> float:
    started = time.perf_counter()
    response = client.post(path, json=payload)
    response.raise_for_status()
    return (time.perf_counter() - started) * 1000


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "p50": statistics.median(values),
        "p95": sorted(values)[max(int(len(values) * 0.95) - 1, 0)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args(argv)
    query = "Ответственность работодателя за задержку заработной платы"
    candidates = [
        {"id": f"a{i}", "text": f"заработная плата задержка работодатель {i}"}
        for i in range(30)
    ]
    with httpx.Client(base_url=args.url, timeout=30) as client:
        embed = [
            _post(client, "/embed", {"texts": [query], "kind": "query"})
            for _ in range(args.n)
        ]
        rerank = [
            _post(client, "/rerank", {"query": query, "candidates": candidates})
            for _ in range(args.n)
        ]
    print({"embed_ms": _summary(embed), "rerank_ms": _summary(rerank)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
