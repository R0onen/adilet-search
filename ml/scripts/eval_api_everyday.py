"""Search quality of a running API on the everyday questions about the added acts.

    python ml/scripts/eval_api_everyday.py <label> <out.jsonl> [--mode hybrid] [--base-url ...]

`data/eval/everyday/queries.jsonl` holds questions in everyday wording about acts outside the
8 main codes, each with the articles that answer it. One row is appended to `<out.jsonl>`; the
rank of the first relevant article for every question is printed for reading.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUERIES = REPO_ROOT / "data/eval/everyday/queries.jsonl"


def search(base_url: str, text: str, lang: str, mode: str) -> tuple[dict, float]:
    body = json.dumps({"query": text, "lang": lang, "mode": mode, "top_k": 10}).encode()
    request = urllib.request.Request(  # noqa: S310 - a URL the operator passes in
        f"{base_url.rstrip('/')}/api/v1/search",
        data=body,
        headers={"Content-Type": "application/json", "X-Session-Id": str(uuid.uuid4())},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        payload = json.load(response)
    return payload, (time.perf_counter() - started) * 1000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("label")
    parser.add_argument("out", type=Path)
    parser.add_argument("--mode", default="hybrid", choices=["hybrid", "semantic", "keyword"])
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    queries = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines()]
    ranks: dict[str, list[int | None]] = {"ru": [], "kk": []}
    latencies: list[float] = []
    degraded = 0
    for query in queries:
        payload, elapsed_ms = search(args.base_url, query["text"], query["lang"], args.mode)
        latencies.append(elapsed_ms)
        degraded += bool(payload.get("degraded"))
        ids = [result["article"]["article_id"] for result in payload["results"]]
        found = [ids.index(article_id) + 1 for article_id in query["relevant"] if article_id in ids]
        rank = min(found) if found else None
        ranks[query["lang"]].append(rank)
        print(f"{query['query_id']} {query['lang']} rank={rank or '-':>2}  {query['text']}")

    def summary(values: list[int | None]) -> dict[str, float | int]:
        n = len(values)
        return {
            "queries": n,
            "hit@1": round(sum(r == 1 for r in values) / n, 3),
            "hit@3": round(sum(r is not None and r <= 3 for r in values) / n, 3),
            "hit@10": round(sum(r is not None for r in values) / n, 3),
            "mrr@10": round(sum(1 / r for r in values if r) / n, 3),
        }

    latencies.sort()
    row = {
        "config": args.label,
        "mode": args.mode,
        **summary(ranks["ru"] + ranks["kk"]),
        "ru": summary(ranks["ru"]),
        "kk": summary(ranks["kk"]),
        "degraded": degraded,
        "p50_ms": round(latencies[len(latencies) // 2]),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
