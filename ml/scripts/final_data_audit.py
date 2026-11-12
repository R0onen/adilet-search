"""Read-only corpus/split checks for the final project; no labels are invented."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    data = ROOT / "data/processed"
    docs = pq.read_table(data / "documents.parquet", columns=["doc_id", "lang"]).to_pylist()
    articles = pq.read_table(
        data / "articles.parquet",
        columns=[
            "article_id",
            "doc_id",
            "unit_key",
            "lang",
            "unit_status",
            "text",
            "parallel_article_id",
        ],
    ).to_pylist()
    chunks = pq.read_table(data / "chunks.parquet", columns=["article_id", "chunk_id"]).to_pylist()
    ids = {a["article_id"] for a in articles}
    groups = {a["article_id"]: f"{a['doc_id']}:{a['unit_key']}" for a in articles}
    queries = [
        json.loads(x)
        for x in (ROOT / "data/eval/queries.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    qrels = [
        json.loads(x)
        for x in (ROOT / "data/eval/qrels.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    splits = json.loads((ROOT / "data/eval/splits.json").read_text(encoding="utf-8"))
    assigned = {}
    for split, qids in splits["query_splits"].items():
        for qid in qids:
            assigned.setdefault(qid, []).append(split)
    group_splits = {}
    for qrel in qrels:
        group = groups[qrel["article_id"]]
        group_splits.setdefault(group, set()).update(assigned.get(qrel["query_id"], []))
    result = {
        "scope": "Data integrity, not legal currentness or human relevance validation.",
        "documents": len(docs),
        "articles": len(articles),
        "chunks": len(chunks),
        "article_languages": dict(Counter(a["lang"] for a in articles)),
        "article_statuses": dict(Counter(a["unit_status"] for a in articles)),
        "duplicate_article_ids": len(articles) - len(ids),
        "duplicate_chunk_ids": len(chunks) - len({c["chunk_id"] for c in chunks}),
        "orphan_chunks": sum(c["article_id"] not in ids for c in chunks),
        "empty_article_texts": sum(not a["text"].strip() for a in articles),
        "parallel_links": sum(bool(a.get("parallel_article_id")) for a in articles),
        "broken_parallel_links": sum(
            bool(a.get("parallel_article_id")) and a["parallel_article_id"] not in ids
            for a in articles
        ),
        "queries": len(queries),
        "query_sources": dict(Counter(q["source"] for q in queries)),
        "queries_without_exactly_one_split": sum(
            len(assigned.get(q["query_id"], [])) != 1 for q in queries
        ),
        "article_groups_crossing_splits": sum(len(s) > 1 for s in group_splits.values()),
        "split_counts": {k: len(v) for k, v in splits["query_splits"].items()},
        "eval_sha256": {
            name: hashlib.sha256((ROOT / "data/eval" / name).read_bytes()).hexdigest()
            for name in ["queries.jsonl", "qrels.jsonl"]
        },
    }
    output = ROOT / "docs/report/final_data_audit.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
