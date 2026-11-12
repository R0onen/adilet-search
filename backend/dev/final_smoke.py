"""Record a real API rehearsal on six source-derived Labor Code questions.

These are diagnostic labels, not independent human gold relevance judgments.
"""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

CASES = [
    ("ru", "Какова нормальная продолжительность рабочего времени?", "a68"),
    ("ru", "Сколько дней ежегодного оплачиваемого отпуска?", "a88"),
    ("ru", "В какие сроки выплачивается заработная плата?", "a113"),
    ("kk", "Жұмыс уақытының қалыпты ұзақтығы аптасына қанша сағат?", "a68"),
    ("kk", "Жыл сайынғы ақы төленетін негізгі еңбек демалысының ұзақтығы қандай?", "a88"),
    ("kk", "Жалақы төлеудің тәртібі мен мерзімдері қандай?", "a113"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18000")
    parser.add_argument("--output", type=Path, default=Path("../docs/report/final_smoke.json"))
    args = parser.parse_args()
    results: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        version = client.get("/api/v1/version").json()
        for mode in ("keyword", "semantic", "hybrid"):
            for lang, query, unit in CASES:
                expected = f"K1500000414:{lang}:{unit}"
                started = time.perf_counter()
                response = client.post(
                    "/api/v1/search", json={"query": query, "lang": lang, "mode": mode}
                )
                body = response.json()
                ids = [r["article"]["article_id"] for r in body.get("results", [])]
                results.append(
                    {
                        "mode": mode,
                        "lang": lang,
                        "query": query,
                        "expected": expected,
                        "status": response.status_code,
                        "wall_ms": round((time.perf_counter() - started) * 1000, 2),
                        "rank": ids.index(expected) + 1 if expected in ids else None,
                        "top_articles": ids,
                        "degraded": body.get("degraded"),
                        "timing_ms": body.get("timing_ms"),
                    }
                )
        for lang, query, _ in (CASES[0], CASES[3]):
            response = client.post("/api/v1/answer", json={"query": query, "lang": lang})
            events = []
            event = None
            for line in response.text.splitlines():
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: "):
                    events.append({"event": event, "data": json.loads(line[6:])})
            answers.append({"lang": lang, "status": response.status_code, "events": events})
    artifact = {
        "created_at": datetime.now(UTC).isoformat(),
        "version": version,
        "scope": "Six source-derived diagnostic questions; no human gold benchmark.",
        "search": results,
        "answers": answers,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for mode in ("keyword", "semantic", "hybrid"):
        subset = [r for r in results if r["mode"] == mode]
        print(
            mode,
            "top1",
            sum(r["rank"] == 1 for r in subset),
            "/",
            len(subset),
            "degraded",
            sum(bool(r["degraded"]) for r in subset),
        )
    print("Answer event sequences:", [[e["event"] for e in a["events"]] for a in answers])
    if any(r["status"] != 200 for r in results) or any(
        not any(e["event"] == "done" for e in answer["events"]) for answer in answers
    ):
        raise SystemExit("Rehearsal failed; inspect the saved HTTP statuses and SSE events")


if __name__ == "__main__":
    main()
