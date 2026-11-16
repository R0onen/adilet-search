# Status: ML

_Last updated: 2026-11-15 · branch `final-completion`_

## Current phase
Final model selected and served: pipeline `1.0.0` (fine-tuned reranker). Assignments 3 and 4 are executed and reported. Remaining: deploy.

## Done
- **Corpus.** `adilet_ml.ingest.adiletcodex` converts AdiletCodex v1.0 (CC BY 4.0, parsed from adilet.zan.kz; Zenodo download with MD5 check, no scraping). Three scopes in `ml/configs/corpus.yaml`:
  - tier 1 (default): 8 codes, 9,259 articles, 16,264 chunks → `data/processed/`; used for training and experiments;
  - tier 2 (`--tier 2`): 40 acts, 20,490 articles, 41,074 chunks; the deployed index;
  - `--all-acts`: 291 acts (51 expired or superseded acts excluded), 41,554 articles, 81,689 chunks; measured, not deployed.
- **Questions.** `data/eval/synthetic/`: 803 LLM-written questions for 400 articles (plain and terminology wording, RU and KK), split by article 70 / 15 / 15. A person reviewed 60 test questions: 53 correct, 3 wrong, 4 vague (`data/eval/labeling/`).
- **Assignment 3** (`ml/notebooks/A3_training_finetuning.ipynb`, `docs/report/A3_report.md`): BM25, LogReg and SVM with tuning; cross-encoder zero-shot, frozen encoder, full fine-tuning; Qwen2.5-0.5B with LoRA.
- **Assignment 4** (`ml/notebooks/A4_embeddings_to_finetuning.ipynb`, `docs/report/A4_report.md`): TF-IDF baseline → E5 embeddings + ML → pretrained cross-encoder → fine-tuned, with paired significance tests and error analysis.
- **Pipeline 1.0.0** (`ml/models/model_manifest.json`, the default): the reranker fine-tuned on written questions (A4, E3b), published as `qb2k/adilet-reranker-mminilm-ru-kk` on the Hugging Face Hub and pinned by revision; 5 candidates at 256 tokens. `index_compat_id` is unchanged, so no reindex is needed to switch between `0.2.0` and `1.0.0`.
- **Final evaluation** through the live API: `docs/report/final_eval.md`, rows in `ml/experiments/final-selection/`. Scripts: `ml/scripts/eval_api_synthetic.py`, `ml/scripts/eval_api_answers.py`.
- **Answer prompt** (`ml/prompts/answer_v1.md`): direct answer when a source states the rule; otherwise a fixed opening sentence, what the sources do say, and what is missing. No bare refusal.
- **LLM rate limits.** On HTTP 429 with a `retry-after` of at most 30 s the service waits and retries once.
- Tests: 64 passed; ruff clean.

## Blockers (need a human)

- A native Kazakh speaker's check of the two fixed sentences in the answer prompt.

## Notes for others (paths, versions, interfaces)
- Manifests: `ml/models/model_manifest.json` (1.0.0, the default), `model_manifest.pretrained.json` (0.2.0, pretrained reranker), `model_manifest.bootstrap.json` (offline stand-ins for tests).
- Select the manifest with `ML_MODEL_MANIFEST_PATH` (compose) or `MODEL_MANIFEST_PATH` (service).
- Corpus: `python ml/scripts/download_data.py [--tier 2] [--out ...]`.
- Model card: `ml/MODEL_CARD.md`. Service: `ml/serving/README.md`.
- GPU runs were done locally on an 8 GB GPU; the notebooks also run on Colab.
