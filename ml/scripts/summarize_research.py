"""Export completed research measurements as a CSV and a presentation-ready Markdown table."""

import argparse
import csv
import json
from pathlib import Path

from research_core import bootstrap_delta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--eval", type=Path)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    if not data["pilot_per_language"]:
        data["scope"] = (
            "Full frozen validation/test split; title-derived proxy labels; body-only corpus"
        )
    if args.eval:
        splits = json.loads((args.eval / "splits.json").read_text(encoding="utf-8"))
        wanted = set(splits["query_splits"]["test"])
        runs = {
            name: json.loads((args.results.parent / (name + "_rankings.json")).read_text())
            for name in data["methods"]
        }
        wanted &= set(runs["e5"])
        labels = {}
        for line in (args.eval / "qrels.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["query_id"] in wanted:
                labels.setdefault(row["query_id"], {})[row["article_id"]] = row["relevance"]
        data["paired_test_ndcg10_delta_vs_e5"] = {
            name: bootstrap_delta(labels, runs["e5"], run)
            for name, run in runs.items()
            if name != "e5"
        }
        data["confidence_interval_resampling_unit"] = "article family; paired RU/KK kept together"
        data["exploratory_pairwise_test_deltas"] = {
            challenger + "_vs_" + baseline: bootstrap_delta(
                labels, runs[baseline], runs[challenger]
            )
            for baseline, challenger in [
                ("bge_m3", "current_hybrid_reranker"),
                ("hybrid_no_reranker", "current_hybrid_reranker"),
            ]
            if baseline in runs and challenger in runs
        }
        args.results.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, method in data["methods"].items():
        row = {"method": name, "revision": method["revision"]}
        for split in ("val", "test"):
            for language in ("all", "ru", "kk"):
                for metric, value in method["splits"][split + ":" + language].items():
                    row[f"{split}_{language}_{metric}"] = value
        rows.append(row)
    with (args.out / "research_comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Research comparison",
        "",
        data["scope"],
        "",
        (
            "Exploratory pilot; too small to establish general retrieval quality."
            if data["pilot_per_language"]
            else "Full frozen split; title labels are not natural-language gold data."
        ),
        "",
        "| Method | Val nDCG@10 | Test nDCG@10 | RU test | KK test | Test MRR@10 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        values = [
            row[k]
            for k in [
                "val_all_ndcg@10",
                "test_all_ndcg@10",
                "test_ru_ndcg@10",
                "test_kk_ndcg@10",
                "test_all_mrr@10",
            ]
        ]
        lines.append("| " + row["method"] + " | " + " | ".join(f"{v:.3f}" for v in values) + " |")
    lines += [
        "",
        "Validation-selected candidate: "
        + data.get("validation_winner", "pending; run incomplete"),
        "",
        "These are our measured results, not numbers copied from model leaderboards.",
        "",
        (
            "The hybrid row reproduces the project's stages on body-only chunks with local BM25; "
            "its IDF differs from Qdrant."
        ),
    ]
    for name, item in data.get("paired_test_ndcg10_delta_vs_e5", {}).items():
        lo, hi = item["ci95"]
        lines.append(
            f"\n{name}: paired test delta {item['mean']:+.3f}, "
            f"bootstrap 95% CI [{lo:+.3f}, {hi:+.3f}]."
        )
    for name, item in data.get("exploratory_pairwise_test_deltas", {}).items():
        lo, hi = item["ci95"]
        lines.append(
            f"\nExploratory {name}: {item['mean']:+.3f}, "
            f"95% CI [{lo:+.3f}, {hi:+.3f}]; no multiplicity correction."
        )
    (args.out / "research_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.out / "research_comparison.md")


if __name__ == "__main__":
    main()
