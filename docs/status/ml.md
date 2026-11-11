# Status: ML agent

_Last updated: 2026-11-11 · ML-01/02 real pipeline (branch `ml/01-real-pipeline`)_

## Current phase
The real pipeline `0.2.0` replaces the bootstrap: official corpus, pretrained E5 embedder,
pretrained cross-encoder reranker, Russian stemming, LLM generation through any OpenAI-compatible
endpoint. Next: A3 (training and fine-tuning notebook for a GPU runtime).

## Done
- **Corpus.** `adilet_ml.ingest.adiletcodex` converts AdiletCodex v1.0 (CC BY 4.0, official texts
  parsed from adilet.zan.kz) to `data_schema.md`. `ml/scripts/download_data.py` downloads it from
  Zenodo, verifies the MD5 and builds `data/processed/`: 8 Tier-1 codes, RU + KK, 16 documents,
  9,259 articles, 16,264 chunks, `corpus_version` 2026.09.17. No scraping of adilet.zan.kz.
- **Sample.** `data/sample/` is now the complete official Labor Code (454 articles, 805 chunks).
  The paraphrased bootstrap sample and its generator are removed.
- **Models (`ml/models/model_manifest.json`, `pipeline_version` 0.2.0, `index_compat_id`
  `e5base-bm25st-ch1`):** `intfloat/multilingual-e5-base` and
  `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, both with pinned revisions. The manifest's
  `runtime` fields select the implementations. `model_manifest.bootstrap.json` keeps the offline
  stand-ins for tests and CI under its own `index_compat_id`.
- **Sparse encoder:** Russian Snowball stemming (PyStemmer), `ё` → `е`. Kazakh is not stemmed.
- **Generator:** the prompt is loaded from `ml/prompts/answer_v1.md` as system + user messages. It
  forbids inference beyond the sources and Markdown, and fixes the refusal sentences.
- **Service:** lifespan startup; a failed model load is reported by `/health` instead of a crash
  loop. Image: CPU torch, pinned `sentence-transformers` / `transformers`, `ml/uv.lock`.
- **Evaluation:** `data/eval/` holds 8,735 title queries with a 70/15/15 split by article
  (`build_title_eval.py`). First real run: BM25 on the test split, nDCG@10 0.730, Recall@50 0.938
  (`ml/experiments/20261111_bm25_title_test`, `ml/reports/results.csv`). The 10-query toy set and
  its three runs are removed.
- Tests: 40 passed; ruff clean.

## In progress
- Latency of the real embedder and reranker on CPU, and the end-to-end check in Docker.

## Next steps
- A3 notebook (Colab GPU): tuned classical models, fine-tuned cross-encoder, frozen-encoder
  transfer learning, LoRA; the best reranker goes into the manifest.
- An LLM-written plain-language question set for a fairer test of the dense and hybrid stages.
- Rewrite the superseded A2/A3/A4 reports and slides from real runs.

## Blockers (need a human)
- A GPU run (Colab/Kaggle) for fine-tuning.
- Human gold labels (`data/eval/labeling/GUIDE.md`) and a Kazakh speaker's review.

## Requests to other agents
| To | Request | Since | Status |
|---|---|---|---|
| Backend | `infra/ml-e5/` and compose service `ml-service-e5` are gone: `ml-service` now runs the real models itself. `ADILET_ML_EMBEDDER_BACKEND` is replaced by `ML_MODEL_MANIFEST_PATH`. A reindex is required (`index_compat_id` changed). | 2026-11-11 | done in this branch |
| Backend | `SEARCH_RERANK_TOP_N=0` is no longer needed: leave it empty to use the manifest's 20. | 2026-11-11 | open |
| Frontend | `data/sample/sample_articles.json` is removed; mocks should not depend on it. | 2026-11-11 | open |

## Notes for others (paths, versions, interfaces)
- Manifests: `ml/models/model_manifest.json` (real), `ml/models/model_manifest.bootstrap.json`.
- Corpus: `python ml/scripts/download_data.py` → `data/processed/`. Sample: `data/sample/`.
- Eval: `data/eval/{queries,qrels}.jsonl`, `splits.json`. Results: `ml/reports/results.csv`.
- Model card: `ml/MODEL_CARD.md`. Service: `ml/serving/README.md`.
- Real article anchors in `source_url` are adilet's own (for example `#z104`).
