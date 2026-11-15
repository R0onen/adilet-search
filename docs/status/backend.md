# Status: Backend

_Last updated: 2026-11-15 · branch `final-completion`_

## Current phase
All backend phases are implemented: public API, admin API, resilience, monitoring, production stack, load test. Remaining: deployment on the public server.

## Done
- **Public API** (`contracts/api.md`): `/search` (hybrid, semantic, keyword), `/answer` (SSE), `/articles`, `/documents`, `/feedback`, `/health`, `/version`.
- **Admin API:** JWT login, usage statistics, query log with filters, detail and CSV export, system status, background reindex with job progress.
- **Query expansion** (`app/services/query_expansion.py`): 34 everyday words and abbreviations get their legal terms appended to the query that goes to the embedder, the reranker, the full-text fallback and the snippet highlighter. The logged, cached and returned query is the user's own. No change to the API contract.
- **Resilience:** PostgreSQL full-text fallback (`degraded: ["semantic"]`), circuit breakers around embed, rerank and Qdrant, a time budget for reranking (`degraded: ["rerank"]`), per-process TTL caches, interrupted reindex jobs marked failed at startup.
- **Indexer:** builds a new collection and switches the alias; stale corpus rows are pruned in batches (a 41 thousand-article corpus exceeded the bind-parameter limit of one statement).
- **Security:** rate limits (search 60/min, answer 10/min, login 5/min), 64 KB body limit, `JWT_SECRET` required in production, `pip-audit` in CI, `docs/tech/security.md`.
- **Monitoring:** `/metrics`, Prometheus with alert rules, provisioned Grafana dashboards.
- **Production stack:** `docker-compose.prod.yml` behind Caddy (HTTPS, security headers), backups, `scripts/smoke.sh`, `scripts/transfer_index.sh` to move a finished index to another machine; `docs/tech/deployment.md`, `docs/tech/runbook.md`.
- **Load test:** `docs/report/load_test.md`: 10 users, cache off, 40-act index, p95 1.2 s.
- **Tests:** 301 unit and contract tests; integration tests on PostgreSQL and Qdrant in CI.

## Not done
- `/admin/stats` timing on 100 thousand log rows is not measured.
- The load test has not been repeated on a 4 vCPU server.

## Blockers (need a human)
- The server address and login for the public deployment.
- A Kazakh speaker should review `NOT_FOUND_TEXT["kk"]` in `backend/app/services/citations.py`.

## Notes for others (endpoints, env vars, how to run)
- **Run everything:** `backend/README.md` → "Run the whole project". Admin, degraded modes and monitoring have their own sections there.
- **API base:** `http://localhost:8000/api/v1` in the development stack, `http://localhost:8080/api/v1` behind the proxy of the production stack; Swagger UI at `/api/v1/docs`.
- **Admin login for local work:** set `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` in `.env` (README, "Admin API").
- **New env vars:** `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `JWT_SECRET`, `JWT_TTL_S`, `RATE_LIMIT_*`, `API_KEYS`, `BREAKER_*`, `CACHE_TTL_S`, `DATA_DIR`, `PROMETHEUS_PORT`, `GRAFANA_*`. All are documented in `.env.example`.
- **Indexer recovery:** `python -m indexer … --abandon-stuck-job` after a crashed CLI run.
- **Windows:** `POSTGRES_PORT=55432` if a native PostgreSQL holds 5432; use `127.0.0.1` in test URLs; prefix container paths with `MSYS_NO_PATHCONV=1` in Git Bash.

