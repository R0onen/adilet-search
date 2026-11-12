"""Compare four retrieval configurations on frozen proxy validation/test queries.

All configurations search the same body-only chunks (no title headers), collapse to articles,
and use the committed relevance labels. Selection uses validation nDCG@10 only. No training,
human-gold or natural-language quality claim is made. Requires the real running ML service.
"""

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import httpx
import numpy as np
import pyarrow.parquet as pq

from adilet_ml.eval.metrics import metric_bundle
from adilet_ml.retrieval.bm25 import BM25Index
from adilet_ml.retrieval.fusion import apply_rerank, fuse

ROOT = Path(__file__).resolve().parents[2]
MODELS = ["bm25_chunks", "e5_chunks", "hybrid_chunks", "hybrid_cross_encoder"]


def sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def embed(client: httpx.Client, texts: list[str], kind: str, batch: int = 64) -> np.ndarray:
    vectors = []
    for start in range(0, len(texts), batch):
        response = client.post(
            "/embed",
            json={
                "texts": [t[:8000] for t in texts[start : start + batch]],
                "kind": kind,
                "return_dense": True,
                "return_sparse": False,
            },
        )
        response.raise_for_status()
        vectors.extend(response.json()["dense"])
        if kind == "passage":
            print(
                f"Body embeddings: {start + len(response.json()['dense'])}/{len(texts)}", flush=True
            )
    return np.asarray(vectors, dtype=np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ml-url", default="http://127.0.0.1:18001")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/report/final_proxy_models.json")
    args = parser.parse_args()
    chunks = sorted(
        pq.read_table(
            ROOT / "data/processed/chunks.parquet",
            columns=["chunk_id", "article_id", "lang", "text"],
        ).to_pylist(),
        key=lambda x: x["chunk_id"],
    )
    queries = read_jsonl(ROOT / "data/eval/queries.jsonl")
    labels = read_jsonl(ROOT / "data/eval/qrels.jsonl")
    splits = json.loads((ROOT / "data/eval/splits.json").read_text(encoding="utf-8"))
    wanted = set(splits["query_splits"]["val"]) | set(splits["query_splits"]["test"])
    queries = [q for q in queries if q["query_id"] in wanted]
    qrels = defaultdict(dict)
    for row in labels:
        if row["query_id"] in wanted:
            qrels[row["query_id"]][row["article_id"]] = row["relevance"]
    cache = ROOT / "data/index/body_eval"
    cache.mkdir(parents=True, exist_ok=True)
    runs = {name: {} for name in MODELS}
    rerank_times = []
    with httpx.Client(base_url=args.ml_url, timeout=180) as client:
        version_response = client.get("/version")
        version_response.raise_for_status()
        version = version_response.json()
        if "bootstrap" in version["pipeline_version"]:
            raise SystemExit("Real pretrained models are required")
        identity = sha({"embedder": version["embedder"], "body_chunks": chunks})
        vector_path = cache / f"{identity}.npy"
        vectors = (
            np.load(vector_path)
            if vector_path.exists()
            else embed(client, [c["text"] for c in chunks], "passage")
        )
        if not vector_path.exists():
            np.save(vector_path, vectors)
        if vectors.shape != (len(chunks), version["embedder"]["dim"]):
            raise RuntimeError("Embedding cache shape mismatch")
        query_vectors = embed(client, [q["text"] for q in queries], "query")
        chunk_by_id = {c["chunk_id"]: c for c in chunks}
        run_identity = sha(
            {
                "vectors": identity,
                "manifest": version,
                "queries": queries,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            }
        )
        checkpoint = cache / f"rankings-{run_identity}.json"
        if checkpoint.exists():
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            runs, rerank_times = saved["runs"], saved["rerank_times"]

        def save_checkpoint() -> None:
            temporary = checkpoint.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"runs": runs, "rerank_times": rerank_times}, ensure_ascii=False),
                encoding="utf-8",
            )
            temporary.replace(checkpoint)

        for lang in ("ru", "kk"):
            positions = np.asarray([i for i, c in enumerate(chunks) if c["lang"] == lang])
            language_chunks = [chunks[i] for i in positions]
            bm25 = BM25Index(k1=1.2, b=0.75).fit(
                [(c["chunk_id"], c["text"]) for c in language_chunks], lang
            )
            language_vectors = vectors[positions]
            query_positions = [i for i, q in enumerate(queries) if q["lang"] == lang]
            score_matrix = query_vectors[query_positions] @ language_vectors.T
            for count, query_position in enumerate(query_positions):
                query = queries[query_position]
                if all(query["query_id"] in runs[name] for name in MODELS):
                    continue
                scores = score_matrix[count]
                indices = np.argsort(-scores, kind="stable")[:50]
                dense = [language_chunks[int(i)]["chunk_id"] for i in indices]
                sparse = [hit.doc_id for hit in bm25.search(query["text"], 50, lang)]
                parameters = dict(k=60, w_dense=1.0, w_sparse=1.0, dense_limit=50, sparse_limit=50)
                for name, mode in [
                    ("bm25_chunks", "keyword"),
                    ("e5_chunks", "semantic"),
                    ("hybrid_chunks", "hybrid"),
                ]:
                    candidates = fuse(mode, dense, sparse, **parameters)
                    runs[name][query["query_id"]] = [c.article_id for c in candidates[:50]]
                head = candidates[:20]
                started = time.perf_counter()
                response = client.post(
                    "/rerank",
                    json={
                        "query": query["text"],
                        "candidates": [
                            {
                                "id": c.article_id,
                                "text": chunk_by_id[c.best_chunk_id]["text"][:8000],
                            }
                            for c in head
                        ],
                    },
                )
                response.raise_for_status()
                rerank_times.append((time.perf_counter() - started) * 1000)
                candidates = apply_rerank(
                    candidates, {r["id"]: r["score"] for r in response.json()["results"]}, 20
                )
                runs["hybrid_cross_encoder"][query["query_id"]] = [
                    c.article_id for c in candidates[:50]
                ]
                if count % 50 == 0:
                    print(f"{lang}: {count + 1}/{len(query_positions)} queries", flush=True)
                    save_checkpoint()
        save_checkpoint()
        if client.get("/version").json() != version:
            raise RuntimeError("The serving manifest changed during evaluation")
    result = {
        "scope": "Title-query proxy, body-only chunks, article ranking. No human gold set.",
        "manifest": version,
        "embedding_cache_id": identity,
        "candidate_limits": {"dense": 50, "sparse": 50, "rerank": 20},
        "body_headers_included": False,
        "splits": {},
        "rerank_ms_median": float(np.median(rerank_times)),
        "queries_sha256": sha(queries),
        "input_char_truncations": sum(len(c["text"]) > 8000 for c in chunks),
        "qrels_file_sha256": hashlib.sha256(
            (ROOT / "data/eval/qrels.jsonl").read_bytes()
        ).hexdigest(),
        "run_identity": run_identity,
    }
    for split in ("val", "test"):
        ids = set(splits["query_splits"][split])
        selected_labels = {k: v for k, v in qrels.items() if k in ids}
        table = {}
        for name in MODELS:
            table[name] = {
                "queries": len(selected_labels),
                **metric_bundle(selected_labels, runs[name]),
            }
            for lang in ("ru", "kk"):
                language_ids = {q["query_id"] for q in queries if q["lang"] == lang}
                table[name].update(
                    {
                        f"{lang}_{k}": v
                        for k, v in metric_bundle(
                            {k: v for k, v in selected_labels.items() if k in language_ids},
                            runs[name],
                        ).items()
                    }
                )
            run_dir = ROOT / f"ml/experiments/20261112_{name}_{split}"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "model": name,
                        "eval": f"title-query (proxy), {split} split, body-only chunks",
                        **table[name],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "config.json").write_text(
                json.dumps(
                    {
                        "manifest": version,
                        "embedding_cache_id": identity,
                        "split": split,
                        "body_headers_included": False,
                        "candidate_limits": result["candidate_limits"],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "rankings.json").write_text(
                json.dumps(
                    {qid: ranking for qid, ranking in runs[name].items() if qid in ids},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        result["splits"][split] = table
    result["selected_by_validation_ndcg10"] = max(
        MODELS, key=lambda name: result["splits"]["val"][name]["ndcg@10"]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["splits"], indent=2), flush=True)
    print("Proxy validation winner:", result["selected_by_validation_ndcg10"], flush=True)


if __name__ == "__main__":
    main()
