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

**Port 5432 already taken?** If a native PostgreSQL runs on your machine, set `POSTGRES_PORT=55432` in `.env`. Only the host-side port changes; containers still use 5432 internally.

## Index data and search

Search needs an index. Until ML publishes `data/sample/`, index the **synthetic** test corpus (invented texts, clearly marked; not legislation):

```bash
docker compose exec backend sh -c "python -m dev.sample_corpus /tmp/sample && python -m indexer --data-dir /tmp/sample"
```

With ML's data (the repo's `data/` is mounted read-only at `/data`):

```bash
docker compose exec backend python -m indexer --data-dir /data/sample
```

Then:

```bash
curl -X POST http://localhost:8000/api/v1/search -H 'Content-Type: application/json' -d '{"query": "Ответственность работодателя за задержку зарплаты"}'
```

Indexer options: `--manifest PATH` (otherwise the manifest comes from `MANIFEST_SOURCE`), `--embeddings PATH` (precomputed `embeddings_{pipeline_version}.parquet`), `--batch-size 64`, `--no-switch` (build without moving the alias), and `--no-prune` (keep DB rows that are not in the data). Exit codes: 0 ok, 1 invalid data or indexing error, 2 another job is running.

The indexer validates the Parquet files against `contracts/data_schema.md` and lists every problem. It then upserts Postgres (unchanged rows are skipped) and builds a **new** collection `legal_chunks__{pipeline_version}` (or a timestamped sibling if that name exists). It checks the point count, records `index_state`, switches the `legal_chunks` alias atomically, and prunes rows that left the corpus. Old collections are kept for rollback. Progress goes to `index_jobs`.

Single-user latency per stage:

```bash
uv run python loadtests/measure_search.py --rounds 1 --top 3
```

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

Needs Postgres, Qdrant and the fake ML service (`docker compose --profile dev up -d postgres qdrant fake-ml`). It creates and resets the `adilet_test` and `adilet_test_search` databases and uses the Qdrant alias `test_legal_chunks`, so dev data is untouched. Override the locations with `TEST_DATABASE_URL`, `TEST_QDRANT_URL` and `TEST_ML_SERVICE_URL` (use `127.0.0.1`, not `localhost`, on Windows). It covers migrations, model-vs-migration drift (`alembic check`), the indexer (first run, same-version rebuild, `--no-switch`, failure keeps the alias, one job at a time, CLI), search (modes, filters, KK, logging), and documents/articles.

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
  services/          search, fusion, snippets, lang, qdrant_store, ml_client, manifest,
                     index_info, query_log, health, background
  db/                SQLAlchemy models, session, repositories
  export_openapi.py  writes ../contracts/openapi.json
indexer/             corpus validation + indexing pipeline + CLI (python -m indexer)
migrations/          Alembic
dev/fake_ml/         fake ML service
dev/sample_corpus.py synthetic test corpus (python -m dev.sample_corpus OUT_DIR)
loadtests/           measure_search.py (single user); locust comes in BE-05
tests/               unit/, contract/, integration/
```
