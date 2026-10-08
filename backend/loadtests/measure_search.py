"""Single-user /search latency: p50/p95 per stage over a fixed query list.

    uv run python loadtests/measure_search.py --base-url http://127.0.0.1:8000 --rounds 1

Sequential requests (one user). The per-stage numbers come from the response's `timing_ms`; `wall`
is measured by this client. Concurrent load tests use locust (BE-05).
"""

import argparse
import statistics
import time
from typing import Any

import httpx

QUERIES = [
    # The three TOR examples first.
    "Ответственность работодателя за задержку зарплаты",
    "Штраф за нарушение экологических норм",
    "Основания расторжения трудового договора",
    "Сроки выплаты заработной платы",
    "Компенсация за задержку выплаты",
    "Когда работодатель может уволить работника",
    "Размер штрафа за выбросы загрязняющих веществ",
    "Жалоба в инспекцию труда",
    "Порядок расчёта компенсации",
    "Трудовые отношения",
    "Жалақыны кешіктіргені үшін жауапкершілік",
    "Еңбек шартын бұзу негіздері",
    "Экологиялық талаптарды бұзғаны үшін айыппұл",
    "Жалақы төлеу мерзімдері",
    "Еңбек инспекциясына шағым",
    "Қызметкерлер санының қысқаруы",
    "Ластаушы заттарды шығару",
    "Өтемақыны есептеу тәртібі",
    "Айлық есептік көрсеткіш",
    "Жұмыс берушінің жауапкершілігі",
]
STAGES = ("embed", "retrieve", "fuse", "rerank", "total")


def percentile(values: list[float], q: float) -> float:
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[int(q) - 1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--rounds", type=int, default=1, help="passes over the 20 queries")
    parser.add_argument("--mode", default="hybrid", choices=["hybrid", "semantic", "keyword"])
    parser.add_argument("--top", type=int, default=0, help="also print the top N per TOR query")
    args = parser.parse_args()

    samples: dict[str, list[float]] = {stage: [] for stage in (*STAGES, "wall")}
    degraded = 0
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        client.post("/api/v1/search", json={"query": "прогрев", "mode": args.mode})  # warm-up
        for _ in range(args.rounds):
            for query in QUERIES:
                started = time.perf_counter()
                response = client.post("/api/v1/search", json={"query": query, "mode": args.mode})
                wall = (time.perf_counter() - started) * 1000
                response.raise_for_status()
                body: dict[str, Any] = response.json()
                samples["wall"].append(wall)
                for stage in STAGES:
                    if stage in body["timing_ms"]:
                        samples[stage].append(body["timing_ms"][stage])
                degraded += bool(body["degraded"])
        version = client.get("/api/v1/version").json()

        if args.top:
            for query in QUERIES[:3]:
                body = client.post(
                    "/api/v1/search", json={"query": query, "mode": args.mode, "top_k": args.top}
                ).json()
                print(f"\n{query}")
                for r in body["results"]:
                    print(
                        f"  {r['rank']}. {r['article']['article_id']}  {r['score']:.4f} "
                        f"({r['score_type']})  {r['doc']['short_title']}. {r['article']['title']}"
                    )

    n = len(samples["wall"])
    print(f"\n{n} requests, mode={args.mode}, degraded={degraded}, pipeline={version}")
    print(f"{'stage':<10}{'p50 ms':>10}{'p95 ms':>10}{'max ms':>10}")
    for stage, values in samples.items():
        if values:
            print(
                f"{stage:<10}{percentile(values, 50):>10.0f}{percentile(values, 95):>10.0f}"
                f"{max(values):>10.0f}"
            )


if __name__ == "__main__":
    main()
