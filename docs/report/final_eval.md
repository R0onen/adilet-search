# Final ML Evaluation

## Scope

This file records the current local evaluation state. A deployed `/api/v1/search` and `/api/v1/answer`
evaluation cannot be completed until Backend wires the ML profile and a deployed/local compose stack
is available.

## Offline Seed Results

| Run | nDCG@10 | Recall@10 | Recall@50 | MRR@10 |
|---|---:|---:|---:|---:|
| `20261008_bm25_seed` | 0.8796 | 0.8889 | 0.9444 | 0.9000 |
| `20261008_hash_dense_seed` | 0.7872 | 0.9444 | 1.0000 | 0.8167 |
| `20261008_tfidf_logreg_seed` | 0.8198 | 1.0000 | 1.0000 | 0.8500 |

## Local Service Latency

| Call | p50 | p95 |
|---|---:|---:|
| `/embed`, 1 query | 3.0 ms | 3.9 ms |
| `/rerank`, 30 candidates | 3.6 ms | 4.6 ms |

## Differences To Check Once API Is Running

- Qdrant sparse IDF may differ from local BM25 IDF.
- Backend collapses chunks to articles and applies filters.
- The answer endpoint trims context and validates citation markers.
- `in_force_only` defaults may remove excluded articles.

## Current Verdict

The local ML side is integration-ready. Final API metrics are blocked by deployment/compose wiring
and real gold labels.
