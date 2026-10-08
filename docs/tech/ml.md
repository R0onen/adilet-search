# ML Technical Documentation

## Pipeline

The ML side owns corpus preparation, retrieval experiments, model manifests and the internal
`ml-service` API. The backend calls:

- `POST /embed` for query and passage vectors;
- `POST /rerank` for candidate article scoring;
- `POST /generate` for grounded answers with numbered citations.

Current manifest: `ml/models/model_manifest.json`, `pipeline_version=0.1.0-bootstrap`,
`index_compat_id=hash-bm25-ch1`.

## Data Flow

1. Target acts are listed in `ml/configs/corpus.yaml`.
2. `ml/scripts/build_corpus.py --fetch` caches Adilet HTML under `data/raw/adilet/{ru,kk}`.
3. `adilet_ml.ingest` parses articles, excluded units and amendment notes.
4. `adilet_ml.chunking` creates article chunks and `text_for_embedding` headers.
5. The contract-shaped Parquet files are written to `data/sample` or `data/processed`.
6. `data/MANIFEST.json` records row counts and checksums.

## Experiments

Seed local experiments are in `ml/experiments/` and aggregate to `ml/reports/results.csv`.

| Run | Purpose |
|---|---|
| `20261008_bm25_seed` | keyword baseline |
| `20261008_hash_dense_seed` | dense-path bootstrap comparison |
| `20261008_tfidf_logreg_seed` | learned reranking baseline |

## Release Procedure

1. Rebuild corpus and write a new `corpus_version`.
2. Run eval scripts and commit run folders with `config.yaml`, `metrics.json`, `env.json`.
3. Pick a pipeline by validation metrics and latency budget.
4. Bump `pipeline_version` in `model_manifest.json`.
5. If embeddings/chunking/sparse encoding changed, bump `index_compat_id` and precompute embeddings.
6. Ask Backend to reindex into a new collection and switch the alias after API evaluation.

## Rollback

Backend keeps previous Qdrant collections. Rollback means switching the alias back to the previous
collection and restoring the matching `model_manifest.json`.

## Known Gaps

- Real Tier-1 corpus and HF artifact upload require `HF_TOKEN` and approved network scraping.
- A3/A4 fine-tuning requires Colab/Kaggle GPU and human labels.
- Final API evaluation requires a deployed backend or local compose stack with the ML profile wired.
