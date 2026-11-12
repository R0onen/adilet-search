"""Write the research narrative from completed, auditable measurements."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / "ml/experiments/research-final"
    results = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    pilot = json.loads(
        (ROOT / "ml/experiments/research-pilot/results.json").read_text(
            encoding="utf-8"
        )
    )
    methods = results["methods"]
    assert "embeddinggemma2" in methods
    table = (ROOT / "docs/report/research-final/research_comparison.md").read_text(
        encoding="utf-8"
    )
    table = "\n".join(line for line in table.splitlines() if line.startswith("|"))
    interval = results["paired_test_ndcg10_delta_vs_e5"]["current_hybrid_reranker"]
    lo, hi = interval["ci95"]
    lines = [
        "# Adilet Search: recent models and retrieval ablations",
        "",
        (
            "Study executed locally on 12 November 2026. This addresses the midterm feedback by "
            "turning the prototype into a controlled retrieval experiment."
        ),
        "",
        "## Questions and design",
        "",
        (
            "Do recent pretrained embeddings improve Russian/Kazakh legal retrieval? Does the "
            "project's lexical fusion and reranker help? Does LLM query rewriting help E5?"
        ),
        "",
        (
            "The complete body-only corpus has 16,264 chunks from 9,259 article-language records. "
            "All candidates see the same frozen 1,311 validation and 1,318 test queries. Parallel "
            "RU/KK article families remain in one split. Queries are titles with known-item proxy "
            "labels, not independently judged everyday questions. The retrieval corpus includes "
            "all source articles, as in an open retrieval system; no own fine-tuning is performed."
        ),
        "",
        (
            "We compare normalized dense vectors with a 512-token encoder budget, language filters "
            "and article-level collapse. E5, Qwen3 and BGE-M3 use FP16; EmbeddingGemma 2 uses "
            "publisher-supported BF16 with its text-only encoder. Tokenizers differ. The hybrid "
            "control reproduces project fusion (RRF 60, equal weights, top 50 dense/sparse) and "
            "reranks 20 candidates using the pinned project cross-encoder. Local BM25 IDF differs "
            "from the production Qdrant backend. It is an offline stage reproduction, not an API "
            "benchmark. No model-specific prompt/length hyperparameter sweep was performed."
        ),
        "",
        "## Full frozen-split measurements",
        "",
        table,
        "",
        (
            "Select by validation, then report test performance. The selected configuration is "
            f"`{results['validation_winner']}`. Against dense E5, its test nDCG@10 difference is "
            f"{interval['mean']:+.3f}, with a paired article-family bootstrap 95% interval "
            f"[{lo:+.3f}, {hi:+.3f}] (2,000 resamples, seed 42)."
        ),
        "",
        (
            "BGE-M3's result is evidence that an alternative dense model is worth investigating; "
            "the measured newer-model configurations do not automatically replace the project's "
            "hybrid approach. Lower scores here do not establish general model inferiority. "
            "Length, language, query style, instructions and numerical precision remain possible "
            "sources of variation, requiring additional controlled experiments."
        ),
        "",
        "Additional pairwise intervals are exploratory, without multiple-comparison correction:",
        "",
    ]
    for name, item in results.get("exploratory_pairwise_test_deltas", {}).items():
        low, high = item["ci95"]
        lines.append(
            f"- `{name}`: {item['mean']:+.3f}, 95% CI [{low:+.3f}, {high:+.3f}]."
        )
    lines += ["", "## LLM rewrite: separate small pilot", ""]
    for name in ("e5", "e5_llm_rewrite"):
        value = pilot["methods"][name]["splits"]["test:all"]
        lines.append(
            f"- `{name}`: test nDCG@10 {value['ndcg@10']:.3f} on "
            f"{value['queries']} matched test queries."
        )
    llm = pilot["methods"]["e5_llm_rewrite"]["llm"]
    lines += [
        "",
        (
            f"The external `{llm}` rewrites only the input query, with no documents, IDs or labels "
            "in its prompt. The fixed pilot has four queries per language per split (16 total); "
            "it is an implementation check and cannot establish a broad LLM effect. No benefit "
            "is established on this pilot. Do not compare its mean directly to the full cohort. "
            "This evaluates LLM-assisted retrieval, not generated-answer faithfulness."
        ),
        "",
        "## Inspectable ranking failures",
        "",
        (
            "Examples below are selected disagreements, not a representative error rate. "
            "Rank `>50` means the expected proxy article is absent from the saved top 50."
        ),
        "",
        "| Language | Title query | Expected proxy article | E5 rank | Hybrid rank | BGE-M3 rank |",
        "|---|---|---|---:|---:|---:|",
    ]
    queries = {
        q["query_id"]: q
        for line in (ROOT / "data/eval/queries.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if (q := json.loads(line))
    }
    labels = {}
    for line in (
        (ROOT / "data/eval/qrels.jsonl").read_text(encoding="utf-8").splitlines()
    ):
        row = json.loads(line)
        labels[row["query_id"]] = row["article_id"]
    runs = {
        name: json.loads((folder / (name + "_rankings.json")).read_text())
        for name in ("e5", "current_hybrid_reranker", "bge_m3")
    }
    test_ids = set(
        json.loads((ROOT / "data/eval/splits.json").read_text())["query_splits"]["test"]
    )
    for lang in ("ru", "kk"):
        for direction in ("hybrid_gain", "hybrid_loss"):
            for qid in sorted(test_ids):
                if queries[qid]["lang"] != lang:
                    continue
                expected = labels[qid]
                ranks = [
                    run[qid].index(expected) + 1 if expected in run[qid] else 51
                    for run in runs.values()
                ]
                e5, hybrid, bge = ranks
                if not (
                    (direction == "hybrid_gain" and hybrid == 1 and e5 > 10)
                    or (direction == "hybrid_loss" and bge == 1 and hybrid > 10)
                ):
                    continue
                title = queries[qid]["text"].replace("|", "/").replace("\n", " ")
                display_ranks = [str(r) if r <= 50 else ">50" for r in ranks]
                lines.append(
                    f"| {lang} | {title} | `{expected}` | "
                    + " | ".join(display_ranks)
                    + " |"
                )
                break
    lines += [
        "",
        (
            "Ranking disagreements identify cases for manual review. They do not, by themselves, "
            "prove a linguistic cause or that every unlabelled retrieved article is irrelevant."
        ),
        "",
        "## Limits and next experiments",
        "",
        (
            "1. Collect independently written RU/KK questions and have native speakers judge pooled "
            "results. One title-based positive per query misses valid alternative legal sources."
        ),
        (
            "2. Compare longer contexts and alternative query instructions on validation only; "
            "reserve a fresh test cohort for confirmation after this exploratory comparison."
        ),
        (
            "3. Scale the matched LLM pilot and measure request cost, latency, failures and semantic "
            "intent preservation. Evaluate cited-answer support separately from retrieval."
        ),
        (
            "4. Measure end-to-end GPU/API performance separately. Corpus cache hits and offline "
            "query/ranking times are recorded, but do not form a fair API p95 comparison."
        ),
        "",
        (
            "The product demo still indexes the Labor Code sample; the research experiment uses "
            "the full corpus independently. Public HTTPS hosting and CPU load acceptance remain "
            "outstanding. All models are pretrained; no project-specific training is claimed."
        ),
        "",
        "## Reproduction and primary sources",
        "",
        (
            "See [run instructions](../tech/research_benchmark.md), "
            "[protocol](RESEARCH_PROTOCOL.md), [machine-readable results]"
            "(../../ml/experiments/research-final/results.json), and "
            "[executed notebook](../../ml/notebooks/Final_Research_Comparison.ipynb). "
            "The results record exact model revisions and corpus/query SHA-256 fingerprints."
        ),
        "",
        "- [Qwen3 model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B).",
        "- [EmbeddingGemma 2 model card](https://huggingface.co/google/embeddinggemma-2).",
        "- [BGE-M3 model card](https://huggingface.co/BAAI/bge-m3).",
        "- [Multilingual E5 model card](https://huggingface.co/intfloat/multilingual-e5-base).",
    ]
    (ROOT / "docs/report/RESEARCH_FINDINGS.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
