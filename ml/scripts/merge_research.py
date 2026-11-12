"""Merge separately executed models only when their corpus and query fingerprints match."""

import argparse
import json
import shutil
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", type=Path, nargs="+")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.inputs]
    identity = ["corpus_sha256", "queries_sha256", "pilot_per_language"]
    for report in reports[1:]:
        if any(report[key] != reports[0][key] for key in identity):
            raise SystemExit("Refusing to compare different corpora or query cohorts")
        for key in ("qrels_sha256", "splits_sha256"):
            if key in report and key in reports[0] and report[key] != reports[0][key]:
                raise SystemExit("Refusing different evaluation labels/splits")
    merged = {**reports[0], "methods": {}, "input_runs": [str(x) for x in args.inputs]}
    args.out.mkdir(parents=True, exist_ok=True)
    for path, report in zip(args.inputs, reports, strict=True):
        for name, method in report["methods"].items():
            if name in merged["methods"]:
                raise SystemExit("Duplicate method in merged results: " + name)
            merged["methods"][name] = {**method, "run_precision": report.get("precision")}
            shutil.copyfile(
                path.parent / (name + "_rankings.json"), args.out / (name + "_rankings.json")
            )
    merged.pop("paired_test_ndcg10_delta_vs_e5", None)
    merged["precision"] = "Per-method supported dtype; inspect dtype/run_precision"
    merged["validation_winner"] = max(
        merged["methods"], key=lambda name: merged["methods"][name]["splits"]["val:all"]["ndcg@10"]
    )
    (args.out / "results.json").write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
