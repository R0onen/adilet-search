# Status: Backend agent

_Last updated: 2026-10-08 · BE-01 skeleton (branch `be/01-skeleton`)_

## Current phase
BE-01: skeleton, dev stack, database, fake ML, OpenAPI stubs. Code complete. Waiting on CI (the GitHub runners have Docker) and human review/merge.

## Done
- `backend/` uv project (Python 3.12, locked): app factory, pydantic-settings config, structlog JSON logs (no client IPs; uvicorn access log disabled), request-id middleware (accepts/creates `X-Request-Id`, also on 500s and CORS preflights), contract error shape for every error (404/405/422/500/501/…), CORS from `CORS_ORIGINS`.
- Pydantic models for every object in `contracts/api.md`. All 16 v1 endpoints are registered with their real models. `/health` and `/version` are real; the rest return `501 not_implemented`.
- `contracts/openapi.json` is generated (`uv run python -m app.export_openapi`, sorted keys). The SSE payloads are published as `SourcesEvent`, `TokenEvent`, `DoneEvent`, `ErrorEvent`. Error responses are documented with `ErrorResponse`; admin routes declare Bearer auth.
- SQLAlchemy models + Alembic migration `0001` for `documents`, `articles` (generated `tsv`: `russian` for ru, `simple` for kk, GIN index), `query_logs` (results/timings as JSONB, indexes for admin stats), `answers`, `feedback` (upsert key with NULLS NOT DISTINCT), `index_jobs` (at most one active job, enforced in the DB), `index_state`, `admin_users`.
- Fake ML service `backend/dev/fake_ml/` per `contracts/ml_service.md`, with `FAKE_ML_FAIL` / latency knobs.
- Dockerfile (multi-stage, uv, non-root, healthcheck); root `docker-compose.yml` (postgres 16.15, qdrant v1.19.2, migrate, backend, fake-ml under `dev`, ml-service/llm placeholders under `ml`); `.env.example`.
- CI `.github/workflows/backend.yml`: ruff, ruff format, mypy, unit + contract tests with coverage, openapi drift; integration tests with postgres/qdrant service containers + fake-ml; a `docker compose --profile dev` smoke test.
- Tests: 125 unit/contract and 10 integration. Every `api.md` example round-trips through the models.
- `api.md` clarifications (additive, see `contracts/CHANGELOG.md` 2026-10-08). Decisions D-012, D-013.

## Verified locally (2026-10-08)
- `uv run pytest`: 125 passed. ruff and mypy clean.
- Integration on a local Postgres 16 (no Docker, via `pgserver`): migrations up/down/up, `alembic check` (no drift), full-text, constraints, live `/health` with fake-ml: 9/10 passed. The one failure is the Qdrant probe, because Qdrant needs Docker, which is broken on this machine (see Blockers).
- **Not yet verified:** `docker compose --profile dev up` and the image build. CI's `compose-smoke` job covers both.

## In progress
- CI run on the `be/01-skeleton` PR.

## Next steps
- BE-02: indexer CLI + search pipeline + documents/articles, on the fake ML until ML ships `data/sample/`, the manifest and `contracts/fixtures/fusion_cases.json`.

## Blockers (need a human)
- **Docker Desktop on the backend dev machine does not start**: the Windows hypervisor is not running (`HypervisorPresent: False`; virtualization is enabled in the BIOS) and WSL has no distributions. A human must fix it in an admin shell and reboot (commands are in the BE-01 hand-off).
- **Deployment target (BE-06, week 5):** no customer VM (D-012), so the team must rent a VPS + domain.

## Requests to other agents
| To | Request | Since | Status |
|---|---|---|---|
| ML | In `docs/status/ml.md`, paste the compose snippet for `ml-service` (port 8001) and `llm` (port 8002): image/build, env, volumes, healthcheck, resources. Placeholders under the `ml` profile in `docker-compose.yml` will be replaced with it. | 2026-10-08 | open |
| ML | Publish `ml/models/model_manifest.json` and `contracts/fixtures/fusion_cases.json` (ML-02). The backend reads the manifest via `MANIFEST_SOURCE=service` (`GET /version`) or `file`. | 2026-10-08 | open |
| ML | Confirm the refusal phrase(s) the prompt template makes the model use, so `/answer` can set `grounded: false` (needed in BE-03). | 2026-10-08 | open |
| Frontend | `contracts/openapi.json` is ready: generate types from it. Confirm that `/admin/stats` covers the dashboard design (open G0 item). | 2026-10-08 | open |

## Notes for others (endpoints, env vars, how to run)
- **API base:** `http://localhost:8000/api/v1`. CORS allows `http://localhost:5173` (`CORS_ORIGINS`, comma list). Swagger UI: `/api/v1/docs`; schema: `/api/v1/openapi.json`.
- **Endpoint state:** `/health` and `/version` are live; everything else returns `501` with `{"error": {"code": "not_implemented", …}}` until BE-02/03/04.
- **Run the stack:** `cp .env.example .env`, then `docker compose --profile dev up -d --build`, then `curl localhost:8000/api/v1/health`.
- **Run without Docker:** see `backend/README.md` ("Run on the host").
- **Fake ML:** `http://localhost:8001` in the dev profile; `FAKE_ML_FAIL=embed|rerank|generate|all` for failure drills.
- **Every response** has `X-Request-Id` (exposed to the browser via CORS). Send your own to correlate logs.
- **`contracts/openapi.json`:** generated 2026-10-08 (app 0.1.0). Regenerated on every API change; CI fails on drift.
- **Deployed URL:** — (BE-06).
