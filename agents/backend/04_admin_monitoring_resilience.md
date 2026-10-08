# BE-04: Admin API, monitoring, resilience, security (week 4)

**Goal: G3.** The admin panel has real data behind it, Grafana shows live metrics, and the system survives the loss of the ML service.

## 1. Admin API (`contracts/api.md` §4)

- **Auth.**
  - `admin_users` is seeded at startup from `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` (bcrypt). Add a CLI `python -m app.cli hash-password`.
  - `POST /admin/login` issues a JWT (HS256, `JWT_SECRET`, 8 h) and is rate-limited to 5/min.
  - A FastAPI dependency protects all `/admin/*` routes: 401 for a missing or invalid token.
- **`GET /admin/stats`.**
  - Use SQL aggregations; `percentile_cont` gives p50/p95.
  - `by_day` is built with `generate_series`, so days without queries show as 0.
  - `top_queries` and `top_zero_result_queries` group by the normalised query.
  - It must answer in < 300 ms on 100k log rows. Add indexes and check with `EXPLAIN`.
- **`GET /admin/queries`** (filters + pagination), **`GET /admin/queries/{id}`** (detail with results, answer, feedback) and **`GET /admin/queries/export`** (streamed CSV, UTF-8 with BOM).
- **`GET /admin/system`:** the health of each component, the pipeline summary from the manifest, the index info (alias → collection, point count, compatibility) and the last job.
- **`POST /admin/reindex`** + **`GET /admin/jobs/{id}`:**
  - runs the BE-02 indexer as a background task, reporting progress through `index_jobs`;
  - only one job at a time (409 otherwise);
  - builds into a new collection and switches the alias only on success. On failure the old index keeps serving.

## 2. Monitoring

- **Backend metrics** (prometheus-fastapi-instrumentator plus custom metrics):

  | Metric | Type | Labels |
  |---|---|---|
  | `search_requests_total` | counter | `mode, lang, status` |
  | `search_stage_latency_seconds` | histogram | `stage = embed\|retrieve\|fuse\|rerank\|assemble\|total` |
  | `search_zero_results_total` | counter | |
  | `degraded_responses_total` | counter | `component` |
  | `answer_ttft_seconds`, `answer_duration_seconds` | histograms | |
  | `answer_citations_invalid_total` | counter | |
  | `feedback_total` | counter | `target, rating` |
  | `ml_client_errors_total` | counter | `endpoint, kind` |
  | `cache_hits_total`, `cache_misses_total` | counters | |

- **`infra/prometheus/prometheus.yml`** scrapes `backend:8000/metrics` and `ml-service:8001/metrics`. Add `infra/prometheus/alerts.yml` with these rules:
  - search p95 > 2 s for 5 min;
  - 5xx rate > 5%;
  - degraded responses > 10%;
  - a component down.
- **Grafana:** provision the datasource and a dashboard JSON (`infra/grafana/dashboards/adilet.json`) with these panels:
  - RPS by endpoint;
  - p50/p95 latency per search stage, with the 2 s reference line;
  - error rate;
  - zero-result rate;
  - degraded rate by component;
  - answer TTFT;
  - feedback ratio;
  - ML service latency.

  Anonymous access is off; the admin password comes from env. Serve Grafana under the `/grafana` sub-path, which is needed for Caddy in BE-06.
- Add `prometheus` and `grafana` to compose under the `monitoring` profile.

## 3. Resilience

- **Full-text fallback** (`services/fts_fallback.py`). When the ML service or Qdrant is unavailable (circuit open, timeout, connection error) or the index is incompatible, `/search` uses Postgres `websearch_to_tsquery` over `articles.tsv` with the same filters. The result has `score_type: fts` and `degraded: ["semantic"]`.
- **Circuit breaker** around the ML client and Qdrant: after N consecutive failures, short-circuit for M seconds, then let one trial request through (half-open). Make it configurable and log state changes.
- **Timeouts per stage** from config. A rerank timeout gives the fused order with `degraded: ["rerank"]`.
- **Compose:** `restart: unless-stopped`, healthchecks, and `depends_on: condition: service_healthy`.
- **Cache:** a TTL LRU (cachetools) for query embeddings and search responses, keyed by (normalised query, lang, mode, filters, top_k, pipeline_version). Clear it on an alias switch. It is per-process; document that limitation.

## 4. Security

- Rate limits per the contract (slowapi; key = session hash + IP hash). `X-API-Key` (keys from env, hashed) gets the higher limits for server-to-server integration.
- Request body size limit (64 KB); CORS allowlist; the security headers are set in Caddy (BE-06).
- `pip-audit` in CI. Write the `docs/tech/security.md` checklist: what is protected and how, and what is out of scope.

## Tests

- Admin auth (no token, bad token, expired token); stats on seeded fixture logs (exact expected numbers); query filters and pagination; the CSV export's header and encoding; the reindex job lifecycle, including the 409.
- **Degraded drills**, run in the integration suite:
  - `FAKE_ML_FAIL=all` → `/search` still returns 200 with `degraded: ["semantic"]`;
  - `FAKE_ML_FAIL=rerank` → `degraded: ["rerank"]`;
  - Qdrant stopped → full-text fallback;
  - the circuit opens and recovers.
- Metrics appear in `/metrics` after a few requests.

## Acceptance criteria (G3)

- [ ] Every admin endpoint is implemented and `openapi.json` is regenerated. Frontend has been told.
- [ ] The Grafana dashboard shows live data during a short locust run (take a screenshot for `docs/presentation/img/`).
- [ ] The manual drill passes: `docker compose stop ml-service`, search still works (degraded), the admin system page shows `ml_service: down`, and after a restart everything recovers.
