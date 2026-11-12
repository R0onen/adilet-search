# Final preparation status — 12 November 2026

Team handoff branch: `final/prototype-and-defense`. See Git history for publication status;
merging to `main` and public hosting are separate steps.

## Completed

- Added production frontend/nginx container and final Compose overlay with Prometheus/Grafana.
- Added per-app backend HTTP metrics and tests; no user query/article IDs in metric labels.
- Fixed blocking ML inference with a bounded worker pool; verified concurrent health responsiveness.
- Pinned ML image dependencies using constraints exported from `uv.lock` and fixed the packaged
  prompt path for LLM generation.
- Fixed nginx Docker DNS resolution after backend recreation and verified recovery.
- Built and ran the real model stack, indexed official Labor Code sample, verified RU/KK retrieval,
  external generated answers, citations, article drawer and parallel-language switching.
- Reused the existing ignored generator configuration, without exposing credentials. Current model:
  `openai/gpt-oss-120b`; fresh checkout defaults to extractive fallback.
- Prepared 10-slide editable presentation, PDF, speaker guide, executed inference notebook,
  technical run guide, readiness matrix and source archive.

## Verification

- 49 ML tests; 258 backend unit/contract checks; 34 database/storage integration checks;
  6 real-model integration checks; 12 frontend unit tests; 4 browser scenarios.
- Backend ruff/format/mypy and OpenAPI drift check passed; frontend build and lint passed.
- Data audit: no duplicate IDs, orphan chunks, empty article texts, broken parallel links or
  article groups crossing evaluation splits. All eval queries are title-derived proxies.
- See `docs/report/final_{runtime,smoke,browser,monitoring,data_audit}.json` for runtime evidence.
- Load runs varied. Latest post-deployment run: 100 requests / 10 users, no HTTP errors,
  60 degraded responses, complete-response p95 2,530.88 ms. Target **not met**.

## Current runtime

- UI: http://127.0.0.1:18080; API docs: http://127.0.0.1:18000/api/v1/docs.
- Grafana: http://127.0.0.1:13000; Prometheus: http://127.0.0.1:19090.
- Current ML service: optional NVIDIA CUDA overlay, one inference worker, rerank 20 candidates.
- Historical CPU preset: 4 workers, 1 CPU thread, rerank 3; its failed load results remain recorded.
- Main demo index: 454 article-language rows / 805 points, pipeline `0.2.0`.
- The full 9,259-article-language / 16,264-chunk corpus is on disk but not in the main demo index.
- The real-ML test uses a separate DB/alias; do not confuse its index with the demo alias.
- Existing unrelated Docker projects retained. Temporary fake-ML test container stopped.

## Next work / outstanding requirements

- The full-corpus frozen proxy comparison is complete; see `docs/report/RESEARCH_FINDINGS.md`.
  Instructor-required project-specific fine-tuning and independent human RU/KK labels remain outstanding. Do not use superseded A3/A4 toy numbers.
- Improve full-pipeline concurrency/performance and measure the full corpus.
- Public HTTPS access for an external grader is unverified; no public URL has been created.
- Planned application admin/auth/full-text failover remains incomplete; monitoring is Grafana.
- See `docs/report/final_readiness.md` for the complete requirement matrix and limitations.

## Research extension

Recent embedding candidates and project ablations now have a matched full-corpus frozen
validation/test study, with pinned checkpoints, per-language metrics, paired uncertainty
and saved rankings. LLM query rewriting is a separate small matched pilot. See
`docs/report/RESEARCH_FINDINGS.md` and `ml/notebooks/Final_Research_Comparison.ipynb`.
The final deck now presents research questions, controls and results alongside the prototype.
