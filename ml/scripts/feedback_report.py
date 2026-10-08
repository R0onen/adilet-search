"""Summarise admin query export rows into retraining candidates."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def _norm(value: str | None) -> str:
    return (value or "").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True, help="admin query export CSV")
    parser.add_argument("--out", type=Path, default=Path("ml/reports/feedback_report.md"))
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)

    zero_results: Counter[str] = Counter()
    negative: Counter[str] = Counter()
    with args.csv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            query = _norm(row.get("query") or row.get("text"))
            if not query:
                continue
            total = _norm(row.get("result_count") or row.get("results_count") or row.get("count"))
            rating = _norm(row.get("rating") or row.get("feedback"))
            if total in {"0", "zero"}:
                zero_results[query] += 1
            if rating.lower() in {"bad", "negative", "-1", "0"}:
                negative[query] += 1

    lines = ["# Feedback Report", ""]
    lines.append("## Top Zero-Result Queries")
    for query, count in zero_results.most_common(args.limit):
        lines.append(f"- {count}x `{query}`")
    lines.append("")
    lines.append("## Top Negative-Rated Queries")
    for query, count in negative.most_common(args.limit):
        lines.append(f"- {count}x `{query}`")
    lines.append("")
    lines.append("Use these as candidates for the next gold-query and fine-tuning batch.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
