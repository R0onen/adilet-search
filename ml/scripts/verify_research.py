"""Independently recompute saved metrics against the current frozen evaluation files."""

import argparse
import hashlib
import json
from pathlib import Path

from adilet_ml.eval.metrics import metric_bundle


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--eval", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.results.read_text(encoding="utf-8"))
    splits = json.loads((args.eval / "splits.json").read_text(encoding="utf-8"))["query_splits"]
    queries = {
        q["query_id"]: q
        for line in (args.eval / "queries.jsonl").read_text(encoding="utf-8").splitlines()
        if (q := json.loads(line))
    }
    labels = {}
    for line in (args.eval / "qrels.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        labels.setdefault(row["query_id"], {})[row["article_id"]] = row["relevance"]
    cohort = None
    checked = 0
    for name, method in report["methods"].items():
        ranking = json.loads((args.results.parent / (name + "_rankings.json")).read_text())
        ids = set(ranking)
        if cohort is None:
            cohort = ids
        if ids != cohort:
            raise ValueError("Mismatched saved query cohorts: " + name)
        if not report["pilot_per_language"] and ids != set(splits["val"] + splits["test"]):
            raise ValueError("Full result lacks frozen validation/test predictions")
        for qid, articles in ranking.items():
            if len(articles) != len(set(articles)):
                raise ValueError("Duplicate articles: " + qid)
            if any(a.split(":")[1] != queries[qid]["lang"] for a in articles):
                raise ValueError("Language filter failed: " + qid)
        for split in ("val", "test"):
            for lang in ("all", "ru", "kk"):
                subset = {
                    q: labels[q]
                    for q in ids & set(splits[split])
                    if lang == "all" or queries[q]["lang"] == lang
                }
                actual = {"queries": len(subset), **metric_bundle(subset, ranking)}
                for metric, value in actual.items():
                    if abs(value - method["splits"][split + ":" + lang][metric]) > 1e-10:
                        raise ValueError(f"Metric mismatch: {name} {split} {lang} {metric}")
                    checked += 1
    report["postrun_verification"] = {
        "metric_values_recomputed": checked,
        "qrels_sha256": digest({q: labels[q] for q in cohort}),
        "splits_sha256": digest(splits),
        "note": "Post-run fingerprints; independently recomputed every saved split metric",
    }
    args.results.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Verified {checked} metric values and matched cohorts/language filters")


if __name__ == "__main__":
    main()
