# Status: Backend agent

_Last updated: 2026-11-12 · BE-04 admin, monitoring, resilience, security (branch `be/04-admin`)_

## Current phase
BE-01 to BE-03, the integration and the real-corpus demo are merged (PRs #1–#8); ML pipeline 0.2.0 is merged (PR #9). **BE-04 is implemented on this branch.** Next: BE-05 (tests, CI, load test), BE-06 (production stack), BE-07 (docs).

## Done in BE-04
- **Admin API (all of `contracts/api.md` §4):** JWT login (bcrypt hash from env, seeded at startup, `python -m app.cli hash-password`), usage statistics, query log with filters, detail and CSV export, system status, background reindex with job progress.
- **Resilience:**
  - Postgres full-text fallback: when the ML service, Qdrant or the index is unavailable, `/search` and `/answer` still answer (`degraded: ["semantic"]`, `score_type: "fts"`).
  - Circuit breakers around embed, rerank and Qdrant.
  - Per-process TTL cache of query embeddings and search responses.
  - A reindex interrupted by an API restart is marked failed at startup.
- **Security:** rate limits (search 60/min, answer 10/min, login 5/min; `X-API-Key` gets 10×), 64 KB body limit, `JWT_SECRET` required in production, `pip-audit` in CI, `docs/tech/security.md`.
- **Monitoring:** `/metrics` (search stages, degraded, zero results, answer TTFT, feedback, ML client errors, cache, HTTP), Prometheus with 4 alert rules, a provisioned Grafana dashboard (10 panels), compose profile `monitoring`.
- **Tests:** 277 unit and contract tests; 60 integration tests, including admin statistics against exact seeded numbers and the degraded drills (ML down, Qdrant down, fallback filters).

## G3 checklist (BE-04 acceptance)
| Criterion | State |
|---|---|
| Every admin endpoint implemented, `openapi.json` regenerated, Frontend told | **Done** (CHANGELOG 2026-11-12). |
| Grafana dashboard shows live data during a short load run | **Not checked yet**: the dashboard is provisioned, but the stack with Grafana has not been run under load. Planned with the BE-05 load test. |
| Manual drill: stop the ML service, search still works, admin shows `ml_service: down`, recovery after restart | **Covered by integration tests** (dead ML URL, dead Qdrant URL). The manual drill on the real stack is still to do. |
| `/admin/stats` under 300 ms on 100k rows | **Not measured.** |

## Next steps
- BE-05: load test (locust), Grafana screenshot, stats timing on 100k rows, coverage.
- BE-06: production compose (reverse proxy, HTTPS-ready, backups), verified locally.
- From Frontend's notes: tell "citation refers to a valid source" apart from "the source supports the claim"; catch refusals phrased outside the fixed sentences.

## Blockers (need a human)
- None. A Kazakh speaker should review `NOT_FOUND_TEXT["kk"]` in `backend/app/services/citations.py`.

## Requests to other agents
| To | Request | Since | Status |
|---|---|---|---|
| Frontend | Regenerate types. Build the admin panel on `/admin/*`. Handle `429` (`Retry-After`), show a notice when `degraded` is not empty, and expect `200` with `degraded: ["semantic"]` where a `503` used to come. | 2026-11-12 | open |
| ML | `/metrics` of the ml-service is scraped by Prometheus (`ml_request_duration_seconds`); keep those metric names. | 2026-11-12 | FYI |

## Notes for others (endpoints, env vars, how to run)
- **Run everything:** `backend/README.md` → "Run the whole project". Admin, degraded modes and monitoring have their own sections there.
- **API base:** `http://localhost:8000/api/v1`; Swagger UI at `/api/v1/docs`. All endpoints of the contract are live.
- **Admin login for local work:** set `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` in `.env` (README, "Admin API").
- **New env vars:** `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `JWT_SECRET`, `JWT_TTL_S`, `RATE_LIMIT_*`, `API_KEYS`, `BREAKER_*`, `CACHE_TTL_S`, `DATA_DIR`, `PROMETHEUS_PORT`, `GRAFANA_*`. All are documented in `.env.example`.
- **Indexer recovery:** `python -m indexer … --abandon-stuck-job` after a crashed CLI run.
- **Windows:** `POSTGRES_PORT=55432` if a native PostgreSQL holds 5432; use `127.0.0.1` in test URLs; prefix container paths with `MSYS_NO_PATHCONV=1` in Git Bash.
