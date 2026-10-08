# BE-01: Skeleton, dev stack, database, fake ML, OpenAPI stubs (week 1)

**Goal:** by G0 the dev stack runs with one command, and `contracts/openapi.json` describes the **whole** v1 API, so the Frontend can generate types even though most endpoints are still stubs.

## Tasks

1. **Project.**
   - `backend/` as a uv project (Python 3.12) with this layout:

     ```
     backend/
       app/
         main.py               app factory, middleware, routers
         core/                 config (pydantic-settings), logging (structlog JSON), errors, security
         api/v1/               routers: search, answer, documents, articles, feedback, health, admin/*
         schemas/              Pydantic models = the contract (one module per area)
         services/             search, answer, fusion, ml_client, qdrant_store, fts_fallback, cache, lang
         db/                   models, session, repositories
         export_openapi.py     writes ../contracts/openapi.json
       indexer/                CLI (BE-02)
       migrations/             Alembic
       dev/fake_ml/            fake ML service (below)
       tests/                  unit/, integration/, contract/
       loadtests/              (BE-05)
       Dockerfile
     ```
   - Add ruff, mypy, pytest and pytest-asyncio.

2. **Cross-cutting concerns.**
   - A request-id middleware (it accepts or creates `X-Request-Id` and returns it).
   - Exception handlers that turn **every** error, including FastAPI's 422, into the contract error shape.
   - Structured JSON logging; CORS from `CORS_ORIGINS`.

3. **Schemas and stubs.**
   - Write Pydantic models for **every** request and response object in `contracts/api.md`, with field descriptions and the example values.
   - Register every endpoint with its real request/response models. The ones not built yet return `501` in the contract error shape.
   - Implement `/api/v1/health` and `/api/v1/version` for real.

4. **OpenAPI export.** `uv run python -m app.export_openapi` writes `contracts/openapi.json` with stable key ordering. Commit it and tell Frontend.

5. **Database.** SQLAlchemy 2 async models and an initial Alembic migration with these tables:
   - `documents (doc_id, lang)` — primary key on the pair;
   - `articles (article_id PK, …, tsv tsvector GENERATED)` — with a GIN index; the `russian` config for `ru` rows, `simple` for `kk`;
   - `query_logs`, `query_results` (or JSONB in `query_logs`), `answers`, `feedback`;
   - `index_jobs`, `index_state`, `admin_users`.

   Follow `contracts/data_schema.md` §3, §4 and §8. Design the columns so the BE-04 admin stats are cheap to compute (indexes on `created_at`, `lang`, `mode`, `zero_results`).

6. **Fake ML service: `backend/dev/fake_ml/`.** A small FastAPI app that obeys `contracts/ml_service.md`:
   - `/embed`: deterministic hash-based dense vectors (dimension from `FAKE_ML_DIM`, default 768, L2-normalised); sparse vectors from lowercase tokens hashed to uint32 with weight 1.0.
   - `/rerank`: token-overlap score.
   - `/generate`: streams a canned answer that cites `[1]`, token by token, with small delays. It also has failure modes driven by env, e.g. `FAKE_ML_FAIL=generate|rerank|all`, used later in the resilience tests.
   - `/version`: a fake manifest with `index_compat_id: "fake"`.

7. **Docker.**
   - `backend/Dockerfile`: multi-stage, uv, non-root, healthcheck on `/api/v1/health`.
   - Root `docker-compose.yml`:
     - `postgres:16` and `qdrant/qdrant:<pinned>`, both with healthchecks and named volumes;
     - `backend`;
     - `fake-ml` under the `dev` profile;
     - placeholders for `ml-service` and `llm` under the `ml` profile, filled in from the ML snippet in week 2.
   - Write `.env.example`.
   - Document the commands in `backend/README.md`.

8. **CI:** `.github/workflows/backend.yml` runs ruff, mypy, pytest (unit), and an **openapi drift check** (regenerate, then `git diff --exit-code contracts/openapi.json`).

9. **Tests:**
   - health and version;
   - error shape for 404 / 422 / 501;
   - request-id propagation;
   - a schema round-trip of every contract example from `api.md`, parsed by the Pydantic models;
   - the fake ML service obeys `ml_service.md` (shape tests).

## Acceptance criteria

- [ ] `docker compose --profile dev up -d` gives healthy postgres, qdrant, fake-ml and backend. `curl localhost:8000/api/v1/health` returns 200.
- [ ] `contracts/openapi.json` is committed and lists every v1 endpoint with its real models. CI is green.
- [ ] `alembic upgrade head` works on a clean DB, and `downgrade base` works too.
- [ ] The status file has the exact run commands and env vars for Frontend and ML.

## Handoff

- **Frontend:** "`openapi.json` is ready; the stub endpoints return 501; the dev API is at `http://localhost:8000/api/v1` with CORS for 5173."
- **ML:** "paste the compose snippet for `ml-service`/`llm` into your status file; I will wire it in."
