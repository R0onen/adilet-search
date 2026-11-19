# Final preparation status — 15 November 2026

Branch: `final-completion`. Requirement matrix and measured results: `docs/report/final_readiness.md`.

## Current state

- **Model.** Pipeline `1.0.0`: multilingual E5 + BM25, reciprocal-rank fusion, the cross-encoder reranker fine-tuned in Assignment 4 (5 candidates, 256 tokens), a dictionary that expands everyday words into legal terms, a hosted LLM for answers. Pipeline `0.2.0` (pretrained reranker) stays available through `ml/models/model_manifest.json`.
- **Corpus.** The live index holds 40 acts: 20,490 articles in Russian and Kazakh, 41,074 chunks (`--tier 2` of the importer). Experiments and training use the 8-code corpus.
- **Assignments 3 and 4.** Notebooks executed on a GPU with outputs; reports rewritten from those runs.
- **Evaluation.** Live API on 195 test questions: right article first for 82.6%, nDCG@10 0.871 (`docs/report/final_eval.md`). 60 test questions reviewed by a person.
- **Load.** 10 users without cache on the 40-act index: p95 1.2 s, no errors, 1 of 981 searches without reranking (`docs/report/load_test.md`).
- **Answers.** No bare refusal: when the articles do not answer the question, the answer says so and reports what they do say. The ML service waits and retries once when the LLM provider rate-limits a request.
- **UI.** About page removed; clearer labels for degraded search; compact header after a search.
- **Presentation.** `docs/presentation/final_deck.pptx` and `.pdf` rebuilt by `build_final.py`; `demo_script.md`, `demo_questions.md` and `final_speaker_guide.md` match the current system.

## Verification

- Backend: 301 unit and contract tests, ruff, mypy. ML: 64 tests. Frontend: 20 tests, lint, build.
- Integration tests (PostgreSQL, Qdrant), the real-model job and the full-stack smoke test run in CI on the pull request.
- Local stack: `docker compose -f docker-compose.prod.yml up -d`, UI at http://localhost:8080.

## Open

- Public deployment: needs the server address and login; steps in `docs/tech/deployment.md`.

- Backup video of the demo.
- A native speaker's check of the fixed Kazakh sentences in `ml/prompts/answer_v1.md`.

## Notes for others

- Pipeline `1.0.0` is the default manifest. Its reranker downloads from the Hugging Face Hub (`qb2k/adilet-reranker-mminilm-ru-kk`) on the first start, like the embedder. `model_manifest.pretrained.json` is pipeline `0.2.0`.
- The hosted LLM's free tier allows 8,000 tokens a minute and 200,000 a day: about two answers a minute and 50 a day. Search does not depend on it.
- The earlier status of 12 November (Labor Code sample index, local ports 18080/18000) is in the Git history of this file.
