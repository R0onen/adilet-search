"""Controlled, resumable embedding/LLM retrieval experiments; run in the GPU ML image.

Only article-body chunks are embedded. Never use this proxy benchmark as human-gold evidence.
"""

import argparse
import gc
import hashlib
import json
import os
import time
from pathlib import Path

import httpx
import numpy as np
import pyarrow.parquet as pq
import torch
from huggingface_hub import model_info
from research_core import article_ranking, bootstrap_delta
from sentence_transformers import SentenceTransformer

from adilet_ml.eval.metrics import metric_bundle
from adilet_ml.retrieval.bm25 import BM25Index
from adilet_ml.retrieval.fusion import apply_rerank, fuse

MODELS = {
    "e5": ("intfloat/multilingual-e5-base", "query: ", "passage: "),
    "qwen3": (
        "Qwen/Qwen3-Embedding-0.6B",
        "Instruct: Retrieve Kazakhstan legislation passages answering the question.\nQuery:",
        "",
    ),
    "bge_m3": ("BAAI/bge-m3", "", ""),
    "embeddinggemma2": (
        "google/embeddinggemma-2",
        "task: search result | query: ",
        "title: none | text: ",
    ),
}


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def rewrite_queries(queries, cache, model):
    """Rewrite without access to documents, qrels, source titles or expected article IDs."""
    base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("LLM_API_KEY")
    if not base or not key:
        raise RuntimeError(
            "LLM rewriting requires the existing server-side generator configuration"
        )
    rewritten = []
    cache.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=90) as client:
        for query in queries:
            path = cache / (
                fingerprint(
                    {
                        "model": model,
                        "query": query["text"],
                        "prompt": "rewrite-v1",
                        "base": base,
                        "max_tokens": 1024,
                        "temperature": 0,
                        "reasoning_effort": "low" if "gpt-oss" in model else None,
                    }
                )
                + ".json"
            )
            if path.exists():
                item = json.loads(path.read_text())
            else:
                started = time.perf_counter()
                response = client.post(
                    base + "/v1/chat/completions",
                    headers={"Authorization": "Bearer " + key},
                    json={
                        "model": model,
                        "temperature": 0,
                        "max_tokens": 1024,
                        **({"reasoning_effort": "low"} if "gpt-oss" in model else {}),
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Rewrite the question as a concise legal search query in its "
                                    "original language. Preserve intent. Do not answer or invent "
                                    "article "
                                    "numbers. Return only the query."
                                ),
                            },
                            {"role": "user", "content": query["text"]},
                        ],
                    },
                )
                response.raise_for_status()
                text = response.json()["choices"][0]["message"]["content"]
                if not text or len(text) > 2000:
                    raise RuntimeError(
                        "Invalid rewrite; failed requests are never replaced silently"
                    )
                item = {"text": text.strip(), "latency_ms": (time.perf_counter() - started) * 1000}
                path.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
            rewritten.append({**query, "text": item["text"]})
    return rewritten


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--eval", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--vector-cache", type=Path)
    p.add_argument("--models", nargs="+", choices=list(MODELS), default=list(MODELS))
    p.add_argument("--pilot-per-language", type=int, default=0)
    p.add_argument("--llm-rewrite", action="store_true")
    p.add_argument("--revisions-from", type=Path, help="Reuse recorded checkpoint commits")
    args = p.parse_args()
    frozen = (
        json.loads(args.revisions_from.read_text(encoding="utf-8"))["methods"]
        if args.revisions_from
        else {}
    )
    np.random.seed(42)
    torch.manual_seed(42)
    if not torch.cuda.is_available():
        raise RuntimeError("This GPU experiment requires infra/start-final.ps1 -Gpu")
    args.out.mkdir(parents=True, exist_ok=True)
    vector_cache = args.vector_cache or args.out
    vector_cache.mkdir(parents=True, exist_ok=True)
    chunks = sorted(
        pq.read_table(
            args.data / "chunks.parquet", columns=["chunk_id", "article_id", "lang", "text"]
        ).to_pylist(),
        key=lambda c: c["chunk_id"],
    )
    queries = [
        json.loads(x)
        for x in (args.eval / "queries.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    splits = json.loads((args.eval / "splits.json").read_text(encoding="utf-8"))["query_splits"]
    selected = []
    for split in ("val", "test"):
        for lang in ("ru", "kk"):
            subset = sorted(
                [q for q in queries if q["query_id"] in splits[split] and q["lang"] == lang],
                key=lambda q: q["query_id"],
            )
            selected.extend(
                subset[: args.pilot_per_language] if args.pilot_per_language else subset
            )
    queries = selected
    ids = {q["query_id"] for q in queries}
    labels = {}
    for line in (args.eval / "qrels.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["query_id"] in ids:
            labels.setdefault(r["query_id"], {})[r["article_id"]] = r["relevance"]
    corpus_hash = fingerprint(chunks)
    report = {
        "precision": "Per-method supported dtype; FP32 stored vectors and cosine scores",
        "confidence_interval_resampling_unit": "article family (parallel RU/KK queries grouped)",
        "scope": "title-derived proxy labels; body-only corpus; pilot is not confirmatory",
        "pilot_per_language": args.pilot_per_language,
        "corpus_sha256": corpus_hash,
        "queries_sha256": fingerprint(queries),
        "qrels_sha256": fingerprint(labels),
        "splits_sha256": fingerprint(splits),
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "methods": {},
    }
    runs = {}
    for name in args.models:
        repo, qp, dp = MODELS[name]
        revision = frozen[name]["revision"] if name in frozen else model_info(repo).sha
        manifest_path = os.getenv("MODEL_MANIFEST_PATH")
        if name == "e5" and name not in frozen and manifest_path and Path(manifest_path).exists():
            revision = json.loads(Path(manifest_path).read_text())["embedder"]["revision"]
        dtype = (
            (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32)
            if name == "embeddinggemma2"
            else torch.float16
        )
        cache_id = fingerprint(
            {
                "corpus": corpus_hash,
                "repo": repo,
                "revision": revision,
                "dtype": str(dtype),
                "max_tokens": 512,
                "passage_prefix": dp,
            }
        )
        path = vector_cache / (cache_id + ".npy")
        cache_hit = path.exists()
        extra = (
            {"config_kwargs": {"vision_config": None, "audio_config": None}}
            if name == "embeddinggemma2"
            else {}
        )
        model = SentenceTransformer(
            repo,
            revision=revision,
            device="cuda" if torch.cuda.is_available() else "cpu",
            trust_remote_code=False,
            model_kwargs={"torch_dtype": dtype},
            **extra,
        )
        model.max_seq_length = 512
        started = time.perf_counter()
        vectors = (
            np.load(path)
            if path.exists()
            else model.encode(
                [dp + c["text"] for c in chunks],
                batch_size=8,
                normalize_embeddings=True,
                show_progress_bar=True,
            ).astype(np.float32)
        )
        if not path.exists():
            np.save(path, vectors)
        if not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) < 0.1):
            raise RuntimeError("Invalid corpus vectors; do not report these measurements")
        corpus_seconds = time.perf_counter() - started
        variants = [(name, queries)]
        if name == "e5":
            variants.append(("current_hybrid_reranker", queries))
            variants.append(("hybrid_no_reranker", queries))
        if args.llm_rewrite and name == "e5":
            llm = os.environ.get("LLM_MODEL")
            if not llm:
                raise RuntimeError("LLM_MODEL is required")
            variants.append(("e5_llm_rewrite", None))
        for variant, questions in variants:
            if questions is None:
                questions = rewrite_queries(queries, args.out / "rewrites", os.environ["LLM_MODEL"])
            started = time.perf_counter()
            qvectors = model.encode(
                [qp + q["text"] for q in questions], batch_size=8, normalize_embeddings=True
            ).astype(np.float32)
            if not np.isfinite(qvectors).all():
                raise RuntimeError("Invalid query vectors")
            score_matrix = qvectors @ vectors.T
            ranking = {
                q["query_id"]: article_ranking(score_matrix[i], chunks, q["lang"])
                for i, q in enumerate(questions)
            }
            if variant in {"current_hybrid_reranker", "hybrid_no_reranker"}:
                indexes = {
                    lang: BM25Index().fit(
                        [(c["chunk_id"], c["text"]) for c in chunks if c["lang"] == lang], lang
                    )
                    for lang in ("ru", "kk")
                }
                bodies = {c["chunk_id"]: c["text"] for c in chunks}
                with httpx.Client(base_url="http://127.0.0.1:8001", timeout=120) as service:
                    for i, query in enumerate(questions):
                        positions = sorted(
                            [j for j, c in enumerate(chunks) if c["lang"] == query["lang"]],
                            key=lambda j: (-float(score_matrix[i, j]), chunks[j]["chunk_id"]),
                        )[:50]
                        dense = [chunks[j]["chunk_id"] for j in positions]
                        sparse = [
                            h.doc_id
                            for h in indexes[query["lang"]].search(query["text"], 50, query["lang"])
                        ]
                        candidates = fuse("hybrid", dense, sparse, k=60, w_dense=1, w_sparse=1)
                        if variant == "hybrid_no_reranker":
                            ranking[query["query_id"]] = [c.article_id for c in candidates[:50]]
                            continue
                        response = service.post(
                            "/rerank",
                            json={
                                "query": query["text"],
                                "candidates": [
                                    {"id": c.article_id, "text": bodies[c.best_chunk_id][:8000]}
                                    for c in candidates[:20]
                                ],
                            },
                        )
                        response.raise_for_status()
                        ordered = apply_rerank(
                            candidates,
                            {r["id"]: r["score"] for r in response.json()["results"]},
                            20,
                        )
                        ranking[query["query_id"]] = [c.article_id for c in ordered[:50]]
            runs[variant] = ranking
            entry = {
                "repo": repo,
                "dtype": str(dtype),
                "revision": revision,
                "max_tokens": 512,
                "query_prefix": qp,
                "passage_prefix": dp,
                "corpus_encoding_seconds_or_cache_load": corpus_seconds,
                "corpus_vector_cache_hit": cache_hit,
                "query_and_ranking_seconds": time.perf_counter() - started,
                "splits": {},
            }
            if variant.endswith("rewrite"):
                entry["llm"] = os.environ["LLM_MODEL"]
                entry["rewrite_prompt"] = "rewrite-v1; no corpus/qrels in prompt"
            for split in ("val", "test"):
                for lang in ("all", "ru", "kk"):
                    subset = {
                        q["query_id"]: labels[q["query_id"]]
                        for q in queries
                        if q["query_id"] in splits[split] and (lang == "all" or q["lang"] == lang)
                    }
                    entry["splits"][split + ":" + lang] = {
                        "queries": len(subset),
                        **metric_bundle(subset, ranking),
                    }
            report["methods"][variant] = entry
            (args.out / (variant + "_rankings.json")).write_text(
                json.dumps(ranking), encoding="utf-8"
            )
            (args.out / "results.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(variant, entry["splits"], flush=True)
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    if "e5" in runs:
        test_labels = {q: r for q, r in labels.items() if q in splits["test"]}
        report["paired_test_ndcg10_delta_vs_e5"] = {
            name: bootstrap_delta(test_labels, runs["e5"], run)
            for name, run in runs.items()
            if name != "e5"
        }
    report["validation_winner"] = max(
        report["methods"], key=lambda name: report["methods"][name]["splits"]["val:all"]["ndcg@10"]
    )
    (args.out / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
