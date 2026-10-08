# Adilet Search backend

FastAPI service behind `/api/v1`: search, streamed RAG answers, documents/articles, feedback, admin.
The public API is specified in [`contracts/api.md`](../contracts/api.md); [`contracts/openapi.json`](../contracts/openapi.json) is generated from this code.

Python 3.12 · uv · FastAPI · Pydantic v2 · SQLAlchemy 2 (async) + Alembic · Qdrant · structlog.

## Run the dev stack (Docker)

From the repo root:

```bash
cp .env.example .env
```

```bash
docker compose --profile dev up -d --build
```

```bash
curl http://localhost:8000/api/v1/health
```

This starts `postgres`, `qdrant`, `fake-ml` (a contract-compliant fake of the ML service), a one-shot `migrate` (Alembic `upgrade head`) and `backend` on `http://localhost:8000`. Swagger UI is at `http://localhost:8000/api/v1/docs`. All ports are bound to `127.0.0.1`.

Stop with `docker compose --profile dev down` (add `-v` to delete the database and Qdrant volumes).

## Run on the host (no Docker for the app)

```bash
cd backend
uv sync
uv run uvicorn app.main:create_app --factory --reload --port 8000
```

The defaults point to `localhost` (Postgres 5432, Qdrant 6333, ML service 8001). Run the fake ML service in a second terminal:

```bash
uv run uvicorn dev.fake_ml.app:app --port 8001
```

Override any setting with an environment variable or a git-ignored `backend/.env` (every variable is documented in the root `.env.example`).

## Tests and checks

```bash
uv run pytest
```

Runs the unit and contract tests (no services needed): error shapes, request ids, CORS, 501 stubs, health logic, the fake ML service against `contracts/ml_service.md`, every example in `contracts/api.md` against the Pydantic models, and OpenAPI freshness.

```bash
uv run pytest -m integration
```

Needs Postgres, Qdrant and the fake ML service (`docker compose --profile dev up -d postgres qdrant fake-ml`). It creates and resets the `adilet_test` database (override with `TEST_DATABASE_URL`, `TEST_QDRANT_URL`, `TEST_ML_SERVICE_URL`). It covers migrations up/down/up, model-vs-migration drift (`alembic check`), full-text configs, DB constraints and live `/health`.

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy app dev
```

## OpenAPI

```bash
uv run python -m app.export_openapi
```

Regenerate after every API change and commit `contracts/openapi.json`. CI fails if it is stale (`--check` verifies without writing).

## Database migrations

```bash
uv run alembic upgrade head
```

```bash
uv run alembic revision --autogenerate -m "describe the change"
```

The schema changes only through migrations. `DATABASE_URL` selects the database.

## Fake ML service

`dev/fake_ml/` implements `contracts/ml_service.md` without models: hash-based dense vectors (texts that share words are close), token-hash sparse vectors, token-overlap rerank, and a canned streamed answer citing `[1]`. Environment:

| Variable | Default | Meaning |
|---|---|---|
| `FAKE_ML_DIM` | `768` | dense dimension |
| `FAKE_ML_FAIL` | empty | `embed`, `rerank`, `generate` or `all` (comma list): those endpoints fail |
| `FAKE_ML_LATENCY_MS` | `0` | extra latency on embed/rerank/first token |
| `FAKE_ML_TOKEN_DELAY_MS` | `20` | delay between streamed tokens |

## Layout

```
app/
  main.py            app factory, middleware, OpenAPI post-processing
  core/              config, logging, errors, request-id middleware
  api/v1/            routers (search, answer, documents, feedback, health, admin/*)
  schemas/           Pydantic models = the contract
  services/          ml_client, qdrant_store, manifest, health (+ search, fusion, … from BE-02)
  db/                SQLAlchemy models and session
  export_openapi.py  writes ../contracts/openapi.json
migrations/          Alembic
dev/fake_ml/         fake ML service
tests/               unit/, contract/, integration/
```
