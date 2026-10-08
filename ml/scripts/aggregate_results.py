"""Aggregate experiment metrics into `ml/reports/results.csv`."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def main() -> int:
    root = Path("ml/experiments")
    out = Path("ml/reports/results.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if root.exists():
        for metrics in sorted(root.glob("*/metrics.json")):
            data = json.loads(metrics.read_text(encoding="utf-8"))
            rows.append({"run": metrics.parent.name, **data})
    fieldnames = sorted({key for row in rows for key in row}) or ["run"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
