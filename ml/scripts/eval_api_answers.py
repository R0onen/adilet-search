"""Generated answers of the live API on the human-approved test questions.

For each question the script calls `POST /api/v1/answer`, reads the event stream and records
whether the labelled article was among the sources, whether the answer cites it, and whether the
backend marked the answer as grounded. Texts are saved so that a person can read them.

    python ml/scripts/eval_api_answers.py out.jsonl [--limit 30] [--base-url http://localhost:8080]

The API allows 10 answers a minute per client, so the script waits between questions.
"""

import argparse
import csv
import json
import statistics
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "data/eval/labeling/synthetic_review.csv"
EVERYDAY = ROOT / "data/eval/everyday/queries.jsonl"
PAUSE_S = 7.0


def approved_questions(limit: int) -> list[dict]:
    with REVIEW.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    verdict = next(name for name in rows[0] if name.startswith("verdict"))
    approved = [row for row in rows if row[verdict].strip().lower() == "ok"][:limit]
    return [{**row, "relevant": [row["article_id"]]} for row in approved]


def everyday_questions(lang: str, limit: int) -> list[dict]:
    """The hand-written everyday questions of one language (`data/eval/everyday/`)."""
    lines = EVERYDAY.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    return [
        {**row, "question": row["text"], "article_id": row["relevant"][0]}
        for row in rows
        if row["lang"] == lang
    ][:limit]


def ask(base_url: str, question: str) -> dict:
    request = urllib.request.Request(  # noqa: S310 - a URL the operator passes in
        f"{base_url}/api/v1/answer",
        data=json.dumps({"query": question, "context_top_k": 5}).encode(),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    events: dict[str, dict] = {}
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        event = ""
        for raw in response:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:") and event != "token":
                events[event] = json.loads(line[5:])
    return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument(
        "--everyday", choices=["ru", "kk"], help="use the everyday questions of this language"
    )
    parser.add_argument("--pause", type=float, default=PAUSE_S, help="seconds per question")
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    rows = []
    items = (
        everyday_questions(args.everyday, args.limit)
        if args.everyday
        else approved_questions(args.limit)
    )
    for item in items:
        started = time.perf_counter()
        try:
            events = ask(args.base_url, item["question"])
        except Exception as exc:  # one failed call must not lose the others
            events = {"error": {"code": type(exc).__name__, "message": str(exc)}}
        sources = events.get("sources", {}).get("sources", [])
        done = events.get("done", {})
        ref = next(
            (s["ref"] for s in sources if s["article"]["article_id"] in item["relevant"]), None
        )
        rows.append(
            {
                "query_id": item["query_id"],
                "lang": item["lang"],
                "question": item["question"],
                "article_id": item["article_id"],
                "label_in_sources": ref is not None,
                "label_cited": ref is not None and ref in done.get("citations", []),
                "citations": done.get("citations", []),
                "grounded": done.get("grounded"),
                "invalid_citations_removed": done.get("invalid_citations_removed"),
                "finish_reason": done.get("finish_reason"),
                "error": events.get("error", {}).get("code"),
                "ttft_ms": done.get("timing_ms", {}).get("ttft"),
                "total_ms": done.get("timing_ms", {}).get("total"),
                "text": done.get("text"),
            }
        )
        print(
            len(rows), item["query_id"], rows[-1]["grounded"], rows[-1]["label_cited"], flush=True
        )
        time.sleep(max(0.0, args.pause - (time.perf_counter() - started)))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    answered = [r for r in rows if r["text"]]
    with_label = [r for r in answered if r["label_in_sources"]]
    summary = {
        "questions": len(rows),
        "answered": len(answered),
        "errors": sum(1 for r in rows if r["error"]),
        "grounded": sum(1 for r in answered if r["grounded"]),
        "label_in_sources": len(with_label),
        "label_cited": sum(1 for r in with_label if r["label_cited"]),
        "invalid_citations_removed": sum(r["invalid_citations_removed"] or 0 for r in answered),
        "ttft_p50_ms": statistics.median(r["ttft_ms"] for r in answered) if answered else None,
        "total_p50_ms": statistics.median(r["total_ms"] for r in answered) if answered else None,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
