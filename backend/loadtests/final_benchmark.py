"""Bounded concurrent search benchmark; errors/degradation cannot silently pass the target.

Example: uv run python loadtests/final_benchmark.py --users 10 --requests 100
"""

import argparse
import asyncio
import json
import math
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

QUERIES = [
    ("ru", "Какова нормальная продолжительность рабочего времени?"),
    ("ru", "Сколько дней ежегодного оплачиваемого отпуска?"),
    ("ru", "В какие сроки выплачивается заработная плата?"),
    ("kk", "Қалыпты жұмыс уақытының ұзақтығы қанша?"),
    ("kk", "Жыл сайынғы ақылы еңбек демалысы қанша күн?"),
    ("kk", "Жалақы төлеу мерзімдері қандай?"),
]


def percentile(values: list[float], quantile: float) -> float | None:
    return sorted(values)[max(0, math.ceil(quantile * len(values)) - 1)] if values else None


async def run(args: argparse.Namespace) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    async with httpx.AsyncClient(base_url=args.base_url, timeout=args.timeout) as client:
        version = (await client.get("/api/v1/version")).json()
        # Warm-up is recorded separately, including any failure.
        warm = await client.post("/api/v1/search", json={"query": QUERIES[0][1]})
        semaphore = asyncio.Semaphore(args.users)

        async def request(index: int) -> None:
            async with semaphore:
                lang, query = QUERIES[index % len(QUERIES)]
                started = time.perf_counter()
                sample: dict[str, Any] = {"index": index, "lang": lang}
                try:
                    response = await client.post(
                        "/api/v1/search",
                        json={"query": query, "lang": lang, "mode": args.mode},
                    )
                    sample["status"] = response.status_code
                    if response.is_success:
                        body = response.json()
                        sample.update(
                            degraded=body.get("degraded", []),
                            results=len(body.get("results", [])),
                            timing_ms=body.get("timing_ms", {}),
                            pipeline_version=body.get("pipeline_version"),
                        )
                except httpx.HTTPError as exc:
                    sample.update(status=0, error=type(exc).__name__)
                sample["wall_ms"] = round((time.perf_counter() - started) * 1000, 2)
                samples.append(sample)

        started = time.perf_counter()
        await asyncio.gather(*(request(i) for i in range(args.requests)))
        elapsed = time.perf_counter() - started
    successful = [s for s in samples if s["status"] == 200]
    full = [s for s in successful if not s["degraded"] and s["results"] > 0]
    p95 = percentile([s["wall_ms"] for s in full], 0.95)
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "client_platform": platform.platform(),
        "base_url": args.base_url,
        "mode": args.mode,
        "users": args.users,
        "requests": args.requests,
        "warmup_status": warm.status_code,
        "version": version,
        "elapsed_s": round(elapsed, 3),
        "requests_per_second": round(len(samples) / elapsed, 3),
        "http_errors": len(samples) - len(successful),
        "degraded_responses": sum(bool(s["degraded"]) for s in successful),
        "empty_responses": sum(s["results"] == 0 for s in successful),
        "full_responses": len(full),
        "full_p50_ms": percentile([s["wall_ms"] for s in full], 0.5),
        "full_p95_ms": p95,
        "target_met": (
            args.users >= 10 and len(full) == args.requests and p95 is not None and p95 <= 2000
        ),
        "scope": "Repeated Labor Code diagnostic questions; not a relevance benchmark.",
        "samples": sorted(samples, key=lambda s: s["index"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18000")
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="hybrid")
    parser.add_argument("--output", type=Path, default=Path("../docs/report/final_load.json"))
    args = parser.parse_args()
    if args.users < 1 or args.requests < args.users:
        parser.error("requests must be >= users >= 1")
    result = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in result.items() if k != "samples"}, indent=2))


if __name__ == "__main__":
    main()
