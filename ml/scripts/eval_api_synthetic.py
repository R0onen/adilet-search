"""Quality of a running API on the synthetic test questions (hybrid mode).

    python ml/scripts/eval_api_synthetic.py <label> <out.jsonl> [--base-url http://localhost:8080]

One row is appended to `<out.jsonl>`: ranking metrics on all test questions, the same on the
questions a person marked as correct (`data/eval/labeling/synthetic_review_summary.json`), the
number of degraded responses and the latency. Labels are automatic: the article a question was
written for is the only relevant one, so report the numbers as "synthetic queries".
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO_ROOT / "data/eval"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def search(base_url: str, query: dict) -> tuple[dict, float]:
    body = json.dumps({"query": query["text"], "lang": query["lang"], "top_k": 10}).encode()
    request = urllib.request.Request(  # noqa: S310 - a URL the operator passes in
        f"{base_url.rstrip('/')}/api/v1/search",
        data=body,
        # A new session per request: the per-session rate limit stays on.
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
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    queries = [q for q in read_jsonl(EVAL_DIR / "synthetic/queries.jsonl") if q["split"] == "test"]
    relevant = {
        row["query_id"]: row["article_id"] for row in read_jsonl(EVAL_DIR / "synthetic/qrels.jsonl")
    }
    review = json.loads(
        (EVAL_DIR / "labeling/synthetic_review_summary.json").read_text(encoding="utf-8")
    )
    approved = set(review["ok_query_ids"])

    totals = {"hit": 0.0, "mrr": 0.0, "ndcg": 0.0, "recall": 0.0}
    human = {"n": 0, "hit": 0.0, "ndcg": 0.0}
    latencies: list[float] = []
    degraded = 0
    for query in queries:
        payload, elapsed_ms = search(args.base_url, query)
        latencies.append(elapsed_ms)
        degraded += bool(payload.get("degraded"))
        ids = [result["article"]["article_id"] for result in payload["results"]]
        is_approved = query["query_id"] in approved
        human["n"] += is_approved
        if relevant[query["query_id"]] not in ids:
            continue
        rank = ids.index(relevant[query["query_id"]]) + 1
        gain = 1 / math.log2(rank + 1)
        totals["recall"] += 1
        totals["mrr"] += 1 / rank
        totals["ndcg"] += gain
        totals["hit"] += rank == 1
        if is_approved:
            human["hit"] += rank == 1
            human["ndcg"] += gain

    n = len(queries)
    latencies.sort()
    row = {
        "config": args.label,
        "queries": n,
        "degraded": degraded,
        "hit@1": round(totals["hit"] / n, 3),
        "mrr@10": round(totals["mrr"] / n, 3),
        "ndcg@10": round(totals["ndcg"] / n, 3),
        "recall@10": round(totals["recall"] / n, 3),
        "human_ok_n": human["n"],
        "human_ok_hit@1": round(human["hit"] / max(human["n"], 1), 3),
        "human_ok_ndcg@10": round(human["ndcg"] / max(human["n"], 1), 3),
        "p50_ms": round(latencies[n // 2]),
        "p95_ms": round(latencies[int(n * 0.95)]),
    }
    print(json.dumps(row))
    with args.out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
