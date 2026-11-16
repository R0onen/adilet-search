# Final project readiness

State on **15 November 2026**. Submission: **23 November 2026**. The sections from "History" down describe the prototype of 12 November (Labor Code sample index, pretrained models) and are kept as a record; where they disagree with this section, this section is current.

## Requirement coverage

| Assignment requirement | Evidence | Open |
|---|---|---|
| Select the final model from earlier experiments | Assignments 3 and 4 (`docs/report/A3_report.md`, `A4_report.md`, executed notebooks): classical models, embeddings + ML, pretrained transformer, full fine-tuning, LoRA, with significance tests and error analysis. Selection through the live API in `ml/experiments/final-selection/`. Embedding-model comparison in `RESEARCH_FINDINGS.md` | – |
| Load a saved model for inference | Pipeline `1.0.0` loads our fine-tuned reranker, published as `qb2k/adilet-reranker-mminilm-ru-kk` on the Hugging Face Hub and pinned by revision in `ml/models/model_manifest.json` | – |
| Handle new inputs correctly | 195 test questions on articles not seen in training; 10 hand-written everyday questions (`docs/presentation/demo_questions.md`); input validation tests | – |
| Fix the model version | Manifest with pinned model revisions, `pipeline_version`, `index_compat_id`; the API reports the version in every response | – |
| Describe inputs and outputs | `contracts/api.md`, `contracts/ml_service.md`, `contracts/openapi.json`, `ml/MODEL_CARD.md` | – |
| API and user interface | FastAPI (`/api/v1`), React UI with search, streamed answers, article viewer, comparison page, admin panel | – |
| Testing | 301 backend unit and contract tests, 64 ML tests, 20 frontend tests; integration tests on PostgreSQL and Qdrant, a real-model job and a full-stack smoke test in CI | – |
| Monitoring | Prometheus metrics per pipeline stage, alerts, provisioned Grafana dashboards, query log in the admin panel | A dashboard screenshot under load for the slides |
| Accessible deployment | `docker-compose.prod.yml` with HTTPS proxy, verified locally end to end; guide in `docs/tech/deployment.md` | Public server: waiting for the server address |
| Technical documentation | `docs/tech/` (architecture, deployment, runbook, security, sizing), contracts, component READMEs, model card | – |
| Final presentation | `docs/presentation/final_deck.pptx` / `.pdf` (10 slides), speaker guide, demo script | Public URL on slide 7; backup video |

## Measured results

| What | Result | Source |
|---|---|---|
| Reranker offline, nDCG@10 (195 test questions) | TF-IDF + LogReg 0.727 → pretrained cross-encoder 0.867 → fine-tuned 0.880 (p = 0.016 against pretrained) | `A4_report.md` |
| Live API, deployed index (40 acts) | right article first for 82.6%, nDCG@10 0.871; on the 53 human-approved questions 83.0% and 0.908 | `final_eval.md` |
| Live API, 55 everyday questions about the added acts | right article first for 58%, in the top 10 for 87% (keyword search: 26% and 64%) | `final_eval.md` |
| Generated answers, 30 human-approved questions and 10 Kazakh ones | 38 of 40 generated; a labelled article cited in 33 of 33 cases where it was retrieved; 27 direct answers, 11 opened with "no direct answer" (overused: see the report) | `final_eval.md` |
| Load, 10 users, cache off | p95 1.2 s, 0 failed, 1 of 981 without reranking | `load_test.md` |

All quality numbers are on LLM-written questions with automatic labels; a person checked 60 of them.

## Open before submission

1. Public deployment (server address needed), then the smoke test and the load test on that server.
2. Backup video of the demo, recorded by the team.
3. A native speaker's check of the fixed Kazakh sentences in the answer prompt.

## History (12 November 2026, prototype on the Labor Code sample)

## Verified operational path

1. Rebuilt the full snapshot from the checksum-verified AdiletCodex download: 16 document-language
   records, 9,259 article-language records and 16,264 chunks, snapshot `2026.09.17`.
2. Built the real ML and backend images; PostgreSQL migrations succeeded.
3. Indexed the **Labor Code sample**: 2 document-language rows, 454 article-language rows,
   805 vector points. Active alias `legal_chunks` points to `legal_chunks__0.2.0` and uses
   `index_compat_id=e5base-bm25st-ch1`. Successful indexing took 142.69 seconds on this run.
4. Exercised all three search modes through the API. On six source-derived RU/KK cases,
   keyword ranked the expected source first in 4/6; semantic and hybrid each did so in 6/6.
   Every diagnostic response was non-degraded in the initial sequential rehearsal. These
   questions were constructed from the expected articles and do not form independent gold data.
5. The initial SSE rehearsal used extractive fallback. The existing generator configuration was
   then recovered without displaying credentials; a direct `openai/gpt-oss-120b` probe returned
   the expected 40-hour fact and a valid source marker. The final end-to-end rehearsal is recorded
   separately below and in `final_smoke.json`; this external model is not trained by our team.
6. Verified the production browser UI: article 68 ranked first, full text contained the working
   hours limit, the drawer switched to Kazakh, and no browser page errors occurred.
7. Verified Prometheus targets `backend` and `ml` as `up` and Grafana's database as healthy.

The complete corpus exists on disk. Only the Labor Code sample is asserted to be in the
demonstration index at this stage. Do not reuse the old bootstrap sample counts or describe
old October runtime checks as current validation.

## Performance and fixes

Hardware: Intel Core i7-14650HX (16 cores / 24 logical processors); Docker reports about
15.42 GiB RAM available. Windows Docker Desktop runs the Linux containers.

The first 60-request hybrid test at 10 concurrent users failed: 44 HTTP errors, 16 degraded
responses and no complete non-degraded responses (`final_load_before.json`). Investigation
found synchronous encoder/reranker work inside async route handlers. The ML routes now offload
inference to a bounded worker pool; a regression test confirms that health requests remain
responsive while inference is blocked.

CPU thread count, inference concurrency and reranker candidate count are being tuned separately.
The four-worker/two-thread/five-candidate run returned all 60 HTTP responses, but 33 were degraded
and complete-response p95 was 2,077.49 ms. It **failed** the acceptance target.

`final_load.json` records the latest run, including errors, degradation and complete-response
latency. `target_met` requires all requests to return non-empty, non-degraded results and p95
≤2,000 ms with at least 10 users. Do not quote the p95 of only successful responses while hiding
the failures. These runs use repeated diagnostic queries on the sample, without a search cache;
they do not demonstrate full-corpus or broad-query performance.

## Submission blockers and scope decisions

- Frozen-split proxy selection is complete; independent human-gold evaluation and any required project-specific training remain outstanding.
  The currently running neural models are pretrained; loading them is not proof of our own
  training. The superseded A3/A4 drafts do not supply that evidence.
- The external grader cannot open a loopback URL. Public hosting needs an actual reachable
  environment; no public URL is currently verified.
- Teammate admin API/UI, full-text fallback and authentication code are merged from `main`;
  earlier runtime reports predate this integration and do not validate their deployment.
- The snapshot is dated; legal currentness and answer faithfulness need separate review.
- Runtime dependency audit: `npm audit --omit=dev` reported zero known vulnerabilities in its
  returned snapshot (`frontend_runtime_audit.json`). The initial full installation audit reported
  11 development dependency findings; no automatic breaking upgrade was applied.

Use `docs/presentation/final_speaker_guide.md` to rehearse without overstating the result.

## Additional evidence

`final_data_audit.json` verifies zero duplicate IDs, empty article texts, orphan chunks, broken
parallel links or article groups crossing evaluation splits. The 8,735 title queries split into
6,106 train, 1,311 validation and 1,318 test queries. All are proxy title queries.

`final_runtime.json` records model/dependency hashes, image IDs and a whitelist of non-secret
runtime settings. The ML image now installs dependencies under constraints exported from
`ml/uv.lock`, while retaining the pinned CPU PyTorch wheel.

## Final local rehearsal

The final CPU preset (4 inference workers, 1 CPU thread, 3 reranked candidates) returned 100/100
HTTP responses in the recorded 10-user run. Two responses were degraded; the other 98 had
p50 1,597.59 ms and p95 1,818.52 ms. The acceptance predicate remained **false** because the
full pipeline did not complete for every request. This is a 454-article-language sample workload,
not a full-corpus benchmark.

With the same three-candidate configuration, sequential diagnostics ranked the expected source
first in 4/6 keyword, 5/6 semantic and 6/6 hybrid cases, all non-degraded. The RU and KK working-
hours answers from the external generator both stated the 40-hour limit and referenced source
`[1]`. Observed answer totals were 1,475 ms RU and 1,309 ms KK for these individual calls. These
checks do not establish general source faithfulness. The first end-to-end generation attempt
exposed a packaged prompt-path error; the image and Compose now explicitly point to the copied
`/app/prompts/answer_v1.md`, and the subsequent API streams completed with `done`.

The submission notebook `Final_Project_Demo.ipynb` executed all five code cells successfully:
health/version, new RU/KK searches, exact article text, streamed answer/reference checking,
and empty-input rejection. The source archive excludes ignored env files and caches and includes
a SHA-256 file manifest. It is a review draft while the model-selection, training and hosting
requirements above remain open.

## Post-deployment check

The latest repeat after deploying the pinned image returned 100 HTTP responses with zero HTTP
errors, but 60 were degraded and the 40 complete responses had p95 **2,530.88 ms**.
`final_load_postdeploy.json` preserves this result and `final_load.json` points to that latest run.
This variability reinforces that the load target is not met; the earlier 98/100 run must not be
presented as the final acceptance result. Use this local prototype as a single-user demonstration.

Recreating the backend exposed nginx's cached container IP, causing 502 responses through the
UI while the direct API was healthy. The production nginx config now resolves Docker DNS with
a bounded cache. A forced backend recreation was followed by a successful version request
through the UI proxy, and the full live browser rehearsal then passed with no page errors.

## Research extension after midterm feedback

The recent-model comparison uses the full 16,264-chunk body-only corpus independently of the
805-point demo index. See [findings](RESEARCH_FINDINGS.md), [protocol](RESEARCH_PROTOCOL.md), and
[run instructions](../tech/research_benchmark.md). Checkpoint revisions, query/corpus hashes,
per-query rankings and article-family bootstrap intervals are saved. No project-specific
training or general natural-language legal accuracy is inferred from title-query scores.
The current local ML service uses the optional GPU configuration; historical CPU load results
remain separate and have not been replaced with an unmeasured GPU throughput claim.

## Integration handoff

The handoff branch incorporates teammate admin/auth, full-text fallback, resilience,
monitoring and training-notebook changes from `origin/main` through `80f1fb7`. Earlier runtime
JSON reports and screenshots predate this integration and do not verify deployment of the
merged application. Git publication and deployment remain distinct steps.
