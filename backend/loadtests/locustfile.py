"""Load test of the public API.

    uv run locust -f loadtests/locustfile.py --host http://127.0.0.1:8000 \
        --headless --users 10 --spawn-rate 2 --run-time 5m --csv loadtests/out/users10

Query mix: 80% hybrid search, 10% keyword search, 10% answers. The questions are the LLM-written
plain-language questions of `data/eval/synthetic/` (falling back to article titles), so the
embedder and the reranker see realistic text and the cache is not hit artificially often.

Each request carries a fresh `X-Session-Id`: it models many visitors, each sending a few
requests, and so stays inside the per-session rate limits, which stay switched on.

`LOADTEST_ANSWER_SHARE=0` turns answers off. With a hosted LLM on a free tier, the provider's
daily token budget allows only a few dozen answers, so answers are off unless asked for.
"""

import json
import os
import random
import uuid
from pathlib import Path

from locust import HttpUser, between, task

REPO_ROOT = Path(__file__).resolve().parents[2]
ANSWER_SHARE = float(os.environ.get("LOADTEST_ANSWER_SHARE", "0"))
SEED = int(os.environ.get("LOADTEST_SEED", "42"))


def load_queries() -> list[str]:
    for path in (
        REPO_ROOT / "data/eval/synthetic/queries.jsonl",
        REPO_ROOT / "data/eval/queries.jsonl",
    ):
        if path.exists():
            rows = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]
            if rows:
                return [row["text"] for row in rows]
    raise SystemExit("no queries: build data/eval first (ml/scripts/build_title_eval.py)")


QUERIES = load_queries()
random.seed(SEED)


class Visitor(HttpUser):
    # A person reads the results before the next question.
    wait_time = between(1, 3)

    def _headers(self) -> dict[str, str]:
        return {"X-Session-Id": str(uuid.uuid4())}

    def _search(self, mode: str) -> None:
        body = {"query": random.choice(QUERIES), "mode": mode, "top_k": 10}  # noqa: S311
        with self.client.post(
            "/api/v1/search",
            json=body,
            headers=self._headers(),
            name=f"/search ({mode})",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            degraded = response.json().get("degraded") or []
            if degraded:
                # A degraded answer is a 200 for the user but a failure for this test:
                # the point is to measure the full pipeline.
                response.failure(f"degraded: {','.join(degraded)}")

    @task(80)
    def search_hybrid(self) -> None:
        self._search("hybrid")

    @task(10)
    def search_keyword(self) -> None:
        self._search("keyword")

    @task(10)
    def answer(self) -> None:
        if random.random() >= ANSWER_SHARE * 10:  # noqa: S311 - this task is 10% of the mix
            self._search("hybrid")
            return
        with self.client.post(
            "/api/v1/answer",
            json={"query": random.choice(QUERIES)},  # noqa: S311
            headers=self._headers(),
            name="/answer",
            stream=True,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            text = response.text
            if "event: done" not in text:
                response.failure("no done event")
