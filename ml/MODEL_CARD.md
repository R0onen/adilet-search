# Model Card: Adilet Search Bootstrap ML Pipeline

Version: `0.1.0-bootstrap`  
Date: 2026-10-08  
Manifest: `ml/models/model_manifest.json`

## Purpose

Adilet Search is a retrieval and RAG pipeline for Russian and Kazakh legislation from Kazakhstan.
This bootstrap pipeline is intended to unblock backend/frontend integration and local assignment
experiments. It is not the final legal-quality model.

## Components

| Component | Current implementation | Intended final path |
|---|---|---|
| Dense embedder | deterministic hash vectors, E5-compatible shape | `intfloat/multilingual-e5-base`, then fine-tuned bi-encoder |
| Sparse encoder | BM25-style hashed sparse vectors | same interface, tuned on full corpus |
| Reranker | lexical overlap fallback | multilingual cross-encoder, then fine-tuned reranker |
| Generator | extractive citation fallback or OpenAI-compatible endpoint | QLoRA/GGUF or GPU endpoint behind the same API |
| Prompt | `ml/prompts/answer_v1.md` | versioned prompt with evaluated citation/refusal behavior |

## Inputs

- `/embed`: 1-128 query or passage strings, RU/KK/mixed text, max 8000 characters.
- `/rerank`: one query and candidate passages/articles.
- `/generate`: a question, language code and numbered sources.

The service rejects empty text, over-limit payloads and non-string values through FastAPI/Pydantic
validation. Long model inputs are truncated to the configured max sequence length.

## Outputs

- `/embed`: dense vectors of length 768, sparse indices/values, truncation flags and model version.
- `/rerank`: candidate ids with scores, sorted descending.
- `/generate`: SSE events or one JSON response with cited text and final usage metadata.

## Data

Committed data is a bootstrap sample:

- `data/sample/documents.parquet`: 2 rows
- `data/sample/articles.parquet`: 30 rows
- `data/sample/chunks.parquet`: 33 rows
- `data/eval/queries.jsonl`: 10 seed synthetic queries
- `data/eval/qrels.jsonl`: seed graded qrels
- `data/eval/splits.json`: deterministic seed split

The sample follows `contracts/data_schema.md`, but it is educational bootstrap text, not the final
official Adilet corpus.

## Metrics

All numbers below come from `ml/experiments/*/metrics.json` and are aggregated in
`ml/reports/results.csv`.

| Run | nDCG@10 | Recall@10 | Recall@50 | MRR@10 | Notes |
|---|---:|---:|---:|---:|---|
| `20261008_bm25_seed` | 0.8796 | 0.8889 | 0.9444 | 0.9000 | lexical baseline |
| `20261008_hash_dense_seed` | 0.7872 | 0.9444 | 1.0000 | 0.8167 | offline dense-path baseline |
| `20261008_tfidf_logreg_seed` | 0.8198 | 1.0000 | 1.0000 | 0.8500 | tiny learned reranker baseline |

Classification metrics for `20261008_tfidf_logreg_seed`:

- `roc_auc`: 0.9072
- `f1`: 0.4898
- `pr_auc`: 0.7118

These are seed-set wiring numbers only. They must not be presented as production quality.

## Latency

Measured locally on Windows CPU with the hash bootstrap service:

| Call | p50 | p95 |
|---|---:|---:|
| `/embed`, 1 query | 3.0 ms | 3.9 ms |
| `/rerank`, 30 candidates | 3.6 ms | 4.6 ms |

Real sentence-transformer and cross-encoder latency still needs a model download and CPU/GPU run.

## Limitations

- Not legal advice; generated answers must be treated as informational assistance only.
- Full Tier-1 official corpus is not yet scraped, reviewed or uploaded.
- Kazakh quality is not human-reviewed.
- The current dense encoder is deterministic hashing, not semantic embeddings.
- The current generator is extractive/fallback, not a fine-tuned LLM.
- Seed qrels are tiny and synthetic; real gold labels are required before quality claims.

## Reproduction

```bash
python -m pip install -e "ml[dev]"
python ml/scripts/create_splits.py
python ml/scripts/run_bm25_baseline.py
python ml/scripts/run_hash_dense_baseline.py
python ml/scripts/run_tfidf_logreg_baseline.py
python ml/scripts/aggregate_results.py
python -m pytest ml/tests
```
