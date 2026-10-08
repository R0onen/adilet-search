# Status: Backend agent

_Last updated: 2026-10-08 · BE-02 indexer + search (branch `be/02-search`)_

## Current phase
BE-02: indexer, search pipeline, documents and articles. Code complete on the fake ML and a synthetic corpus. The G1 items that need ML's real sample and service v0 are still open (see "G1 checklist").

## Done
- **BE-01** merged (PR #1); CI green on `main`.
- **Indexer** `python -m indexer` (`backend/indexer/`): validates the Parquet files against `data_schema.md` §3–5 and reports every problem at once. It upserts `documents`/`articles` (unchanged rows skipped), builds a new Qdrant collection per §8 (named `dense` + `sparse` vectors, HNSW m=16/ef 128, IDF modifier, payload indexes), gets vectors from precomputed embeddings (pipeline_version checked) or `/embed` (batched, 3 retries), and checks the point count. It then records `index_state`, switches the alias atomically, and prunes rows that left the corpus. Progress is written to `index_jobs`; at most one job runs at a time. Reusable by the BE-04 admin reindex.
- **Search** `POST /search`: language detection (contract rule), embed with only the vectors the mode needs, dense + sparse retrieval in parallel with payload filters (lang, doc_ids, doc_types, in-force = act in force and article not excluded, adoption-date range), weighted RRF + collapse exactly per `ml_service.md` §2, rerank of the head, assembly from Postgres in one query, snippets (≤ 300 chars, verbatim) and highlights. Per-stage time budgets (env). Rerank failure or timeout → fused order + `degraded: ["rerank"]`. Embed/Qdrant failure, no index, or an incompatible `index_compat_id` → `503 upstream_unavailable` (the full-text fallback is BE-04).
- **`GET /documents`** (filters, pagination, title search), **`/documents/{doc_id}`** (TOC in order), **`/articles/{article_id}`** (verbatim text, notes, parallel/prev/next).
- **Query logging** off the request path (also for failed searches): query, normalised query, lang, mode, filters, results (ids, scores, titles), timings, degraded, error code, pipeline_version, client (web/api-key/unknown), HMAC session hash.
- **Qdrant over gRPC** (D-014): retrieve went from 46 ms to 2 ms per request.
- Synthetic test corpus `python -m dev.sample_corpus OUT_DIR` (invented texts, marked as such; not legislation). Single-user latency script `loadtests/measure_search.py`.
- CI: integration tests now cover the indexer and search. The compose smoke test indexes the synthetic corpus inside the container and checks search, KK search, documents and articles end to end.
- Decisions D-014, D-015. CHANGELOG entry 2026-10-08 (BE-02).

## G1 checklist (BE-02 acceptance)
| Criterion | State |
|---|---|
| `python -m indexer --data-dir data/sample` with `--profile ml` succeeds and the alias points to the new collection | **Waiting on ML** (no `data/sample/`, no ml-service). Verified with the synthetic corpus + fake ML in the compose stack: 16 points, alias → `legal_chunks__0.0.0-fake`, 4.9 s. |
| The three TOR queries return plausible articles (top 3 in this file) | **Waiting on ML** for real data. On the synthetic corpus + fake ML, each TOR query ranks the matching synthetic article first (below). |
| `/search` p50/p95 per stage, single user, 20 queries | Measured on fake ML + synthetic corpus only (below). Real-model numbers are pending ML v0. |
| `openapi.json` regenerated; Frontend told | Done (CHANGELOG 2026-10-08 BE-02). |

**TOR queries, synthetic corpus + fake ML (NOT real models or law):**
1. «Ответственность работодателя за задержку зарплаты» → 1. `T0000000001:ru:a114` (synthetic "liability for wage delay"), 2. `T0000000002:ru:a10`, 3. `T0000000001:ru:a52`.
2. «Штраф за нарушение экологических норм» → 1. `T0000000002:ru:a10` (synthetic "fines for environmental violations"), 2. `T0000000001:ru:a114`, 3. `T0000000001:ru:a52`.
3. «Основания расторжения трудового договора» → 1. `T0000000001:ru:a52` (synthetic "grounds for termination"), 2. `T0000000001:ru:a1`, 3. `T0000000002:ru:a10`.

**Latency, single user, 20 queries (10 RU + 10 KK), dev laptop (i7-13700HX, Docker Desktop/WSL2), fake ML, 16-chunk synthetic index, 2026-10-08.** These numbers show pipeline overhead only, not model cost:

| Stage | p50 ms | p95 ms |
|---|---|---|
| embed | 2 | 2 |
| retrieve | 2 | 3 |
| fuse | 0 | 0 |
| rerank | 2 | 2 |
| total (server) | 8 | 9 |
| wall (client) | 11 | 13 |

Before the gRPC switch: retrieve 46/49 ms, total 53/56 ms.

## In progress
- PR for `be/02-search`.

## Next steps
- When ML ships `data/sample/`, `model_manifest.json`, the ml-service snippet and `fusion_cases.json`: wire `ml-service`/`llm` into compose (profile `ml`), index the sample, paste the real TOR top 3 and real latencies here, and run the `@pytest.mark.ml` test.
- BE-03: `/answer` (SSE), feedback, full query logging.

## Blockers (need a human)
- None for backend work. G1 needs ML's sample + service v0 (see Requests).

## Requests to other agents
| To | Request | Since | Status |
|---|---|---|---|
| ML | In `docs/status/ml.md`, paste the compose snippet for `ml-service` (port 8001) and `llm` (port 8002): image/build, env, volumes, healthcheck, resources. The placeholders under the `ml` profile in `docker-compose.yml` will be replaced with it. | 2026-10-08 | open |
| ML | Publish `data/sample/`, `ml/models/model_manifest.json` and `contracts/fixtures/fusion_cases.json`. The backend already runs the fixture automatically once the file exists (`tests/unit/test_fusion.py`). **Proposed format:** `{"cases": [{"name", "mode": "hybrid\|semantic\|keyword", "params": {"rrf_k", "weights": {"dense", "sparse"}, "dense_limit"?, "sparse_limit"?, "rerank_top_n"?}, "dense": [chunk_id…], "sparse": [chunk_id…], "rerank_scores"?: {article_id: score}, "expected": [{"article_id", "best_chunk_id"?, "score"?}]}]}`. Article ids come from chunk ids by stripping `:c{n}`. | 2026-10-08 | open |
| ML | Confirm two `data_schema.md` §8 details implemented by Backend (CHANGELOG 2026-10-08 BE-02, D-015): timestamped collection names for same-version rebuilds; `corpus_version` on articles taken from their document. | 2026-10-08 | open |
| ML | Confirm the refusal phrase(s) the prompt template makes the model use, so `/answer` can set `grounded: false` (needed in BE-03). | 2026-10-08 | open |
| Frontend | Regenerate types: `/search`, `/documents`, `/documents/{doc_id}` and `/articles/{article_id}` are live; `timing_ms` keys are optional non-null integers. Confirm that `/admin/stats` covers the dashboard design (open G0 item). | 2026-10-08 | open |

## Notes for others (endpoints, env vars, how to run)
- **API base:** `http://localhost:8000/api/v1`. CORS allows `http://localhost:5173`. Swagger UI: `/api/v1/docs`.
- **Live:** `/health`, `/version`, `/search`, `/documents`, `/documents/{doc_id}`, `/articles/{article_id}`. **Stubs (501):** `/answer`, `/feedback`, `/admin/*`.
- **Searchable dev stack without ML data:** `docker compose --profile dev up -d --build`, then `docker compose exec backend sh -c "python -m dev.sample_corpus /tmp/sample && python -m indexer --data-dir /tmp/sample"`. The synthetic ids start with `T000000000` and the titles say "синтетические данные / синтетикалық деректер". Do not use them as real law in mocks or screenshots.
- **Index ML data:** `docker compose exec backend python -m indexer --data-dir /data/sample` (the repo's `data/` is mounted read-only at `/data`). Add `--embeddings /data/index/embeddings_<v>.parquet` for precomputed vectors.
- **Windows:** if a native PostgreSQL holds 5432, set `POSTGRES_PORT=55432` in `.env`. Use `127.0.0.1` rather than `localhost` in test URLs.
- **New env vars:** `SEARCH_EMBED_TIMEOUT_S` (2), `SEARCH_RETRIEVE_TIMEOUT_S` (2), `SEARCH_RERANK_TIMEOUT_S` (1.5), `INDEX_STATE_TTL_S` (30), `QDRANT_PREFER_GRPC` (true), `QDRANT_GRPC_PORT` (6334).
- **Deployed URL:** — (BE-06).
