# ML Assignment Status

> **Superseded (2026-11-11).** The numbers in this draft came from a 10-query toy set on a paraphrased sample. That set and its runs were removed. Current results are in `ml/reports/results.csv`; this document is rewritten in the A3/A4 phases.

Date: 2026-10-08

## Completed In Repo

- Corpus/sample schema and committed bootstrap data.
- ML service v0 endpoints and tests.
- Model manifest and prompt template.
- Fusion fixture shared with Backend.
- Seed eval queries, qrels and deterministic splits.
- BM25, hash-dense and TF-IDF/logistic local baselines.
- Experiment run folders and aggregated results table.
- Model card, technical ML docs, A2/A3/A4/final-eval report files and slide drafts.

## Verified

- `python -m pytest ml/tests`: 30 passed.
- `python -m ruff check ml/src ml/tests ml/scripts`: passed.
- `python -m pytest backend/tests/unit/test_fusion.py`: 19 passed.

## Not Fully Completable Locally

- Full official Tier-1 Adilet corpus scrape and HF upload.
- 150+ human-labelled gold queries with agreement.
- A3/A4 transformer fine-tuning and QLoRA runs.
- Final `v1.0.0` model checkpoint, precomputed embeddings and deployed API evaluation.

These require external credentials, human labeling and GPU/runtime access.
