# Status: ML agent

_Last updated: 2026-10-08 - local ML assignment package_

## Current phase
ML-01/02 bootstrap is ready for integration. ML-03/A2 has seed splits, baselines and run folders.
A3/A4/ML-07 local documentation is complete, but real Adilet scraping, HF upload, human labels,
GPU fine-tuning and deployed API evaluation are still external blockers.

## Done
- Scaffolded `ml/` as a Python package with retrieval helpers, ingestion/chunking stubs, tests,
  Dockerfile and service README.
- Released `data/sample/` bootstrap corpus: 2 documents, 30 articles, 33 chunks,
  `corpus_version=2026.10.08-bootstrap`.
- Added `data/MANIFEST.json` with SHA-256 checksums and `ml/reports/data_quality.md`.
- Added `ml/models/model_manifest.json`, `pipeline_version=0.1.0-bootstrap`,
  `index_compat_id=hash-bm25-ch1`.
- Implemented ML-owned FastAPI service: `/health`, `/version`, `/metrics`, `/embed`, `/rerank`,
  `/generate` streaming and non-streaming.
- Added `ml/prompts/answer_v1.md`. Refusal phrases:
  - RU: `В предоставленных источниках нет ответа.`
  - KK: `Берілген дереккөздерде жауап жоқ.`
- Added `contracts/fixtures/fusion_cases.json`; backend unit fixture test passes.
- Added Adilet parser/corpus builder for cached RU/KK HTML plus Tier-1 targets in
  `ml/configs/corpus.yaml`.
- Added seed retrieval eval under `data/eval/`, frozen `splits.json`, and baseline runners for
  BM25, hash-dense and TF-IDF/logistic reranking.
- Added `ml/experiments/*_seed/`, `ml/reports/results.csv`, `ml/MODEL_CARD.md`, A2/A3/A4 report
  drafts, final eval notes, technical ML docs, slide drafts and defence Q&A.
- Confirmed Backend's BE-02 index details: timestamped same-version rebuild collections are OK;
  article `corpus_version` may be derived from the document row.

## In progress
- Real corpus pipeline: target list exists in `ml/configs/corpus.yaml`; scraping still needs
  approved network access and parser QA.
- Real model path: service can switch to `sentence-transformers`, but revisions are not pinned yet.

## Next steps
- Verify every Tier-1 `doc_id` live on adilet.zan.kz, then scrape/cache RU+KK pages politely.
- Replace bootstrap text with official parsed Adilet text in `data/processed/` and refresh
  `data/sample/` from the real Labor Code.
- Fetch/pin E5 and cross-encoder revisions, measure real CPU latency, and update the manifest.
- Expand `data/eval/` from the seed set to at least 200 reviewed RU/KK queries.

## Blockers (need a human)
- HF namespace and `HF_TOKEN` for private dataset/model artifacts.
- Approval/network path for live Adilet scraping and model downloads.
- Human review for Kazakh text and future gold labels.
- GPU/Colab/Kaggle run for fine-tuning phases.

## Requests to other agents
| To | Request | Since | Status |
|---|---|---|---|
| Backend | Wire the compose snippet below under an `ml` profile when ready, then index `data/sample/` with `MANIFEST_SOURCE=service` or the manifest file. | 2026-10-08 | open |
| Frontend | Use `data/sample/sample_articles.json` for realistic article mocks until the real scraped sample replaces it. | 2026-10-08 | open |

## Notes for others (paths, versions, interfaces)
- Sample data: `data/sample/{documents,articles,chunks}.parquet`,
  `data/sample/sample_articles.json`.
- Data manifest: `data/MANIFEST.json`.
- ML manifest: `ml/models/model_manifest.json`.
- Fusion fixture: `contracts/fixtures/fusion_cases.json`.
- Seed eval: `data/eval/{queries,qrels}.jsonl` and `data/eval/labeling/GUIDE.md`.
- Seed splits: `data/eval/splits.json`.
- Results table: `ml/reports/results.csv`.
- Model card: `ml/MODEL_CARD.md`.
- Assignment status: `docs/report/ASSIGNMENT_STATUS.md`.
- Current `pipeline_version`: `0.1.0-bootstrap`.
- Current `index_compat_id`: `hash-bm25-ch1`.
- Service run command:
  `python -m uvicorn adilet_ml.serving.app:app --app-dir ml/src --host 0.0.0.0 --port 8001`.
- Seed baseline commands:
  `python ml/scripts/create_splits.py`;
  `python ml/scripts/run_bm25_baseline.py`;
  `python ml/scripts/run_hash_dense_baseline.py`;
  `python ml/scripts/run_tfidf_logreg_baseline.py`;
  `python ml/scripts/aggregate_results.py`.
- Compose snippet:

```yaml
  ml-service:
    build:
      context: ./ml
      dockerfile: serving/Dockerfile
    environment:
      MODEL_MANIFEST_PATH: /app/models/model_manifest.json
      MODEL_CACHE_DIR: /models
      ADILET_ML_EMBEDDER_BACKEND: hash
      ADILET_ML_GENERATOR_MODE: fallback
      LLM_BASE_URL: http://llm:8002
      LLM_MODEL: adilet-generator
      LLM_API_KEY: ${LLM_API_KEY:-}
    volumes:
      - ./ml/models:/app/models:ro
      - ml-model-cache:/models
    ports:
      - "8001:8001"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health').read()"]
      interval: 10s
      timeout: 5s
      retries: 6
```

## Measured latencies (CPU, local Windows, hash bootstrap)
| Call | p50 | p95 | Model / pipeline version | Date |
|---|---:|---:|---|---|
| `/embed`, 1 query | 3.0 ms | 3.9 ms | hash bootstrap / `0.1.0-bootstrap` | 2026-10-08 |
| `/rerank`, 30 candidates | 3.6 ms | 4.6 ms | lexical overlap / `0.1.0-bootstrap` | 2026-10-08 |
| `/embed`, 64 passages | not measured | not measured | pending real indexing benchmark | 2026-10-08 |
| `/generate` | not measured | not measured | fallback/LLM pending | 2026-10-08 |

## Seed retrieval baseline
| Run | Queries | nDCG@10 | Recall@10 | Recall@50 | MRR@10 | Date |
|---|---:|---:|---:|---:|---:|---|
| `20261008_bm25_seed` | 10 | 0.8796 | 0.8889 | 0.9444 | 0.9000 | 2026-10-08 |
| `20261008_hash_dense_seed` | 10 | 0.7872 | 0.9444 | 1.0000 | 0.8167 | 2026-10-08 |
| `20261008_tfidf_logreg_seed` | 10 | 0.8198 | 1.0000 | 1.0000 | 0.8500 | 2026-10-08 |

This is a seed wiring benchmark over the bootstrap sample, not a production quality benchmark.
