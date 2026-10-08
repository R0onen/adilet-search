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

## Run the whole project (real ml-service + ML's data + UI)

Use the real ml-service (profile `ml`, built from `ml/`) instead of the fake one, and point the backend at it. In bash:

```bash
docker compose --profile dev stop fake-ml
```

```bash
ML_SERVICE_URL=http://ml-service:8001 docker compose --profile ml up -d --build
```

In PowerShell, set the variable first (`$env:ML_SERVICE_URL = "http://ml-service:8001"`) and then run `docker compose --profile ml up -d --build`. Index ML's sample with ML's models:

```bash
docker compose exec backend python -m indexer --data-dir /data/sample
```

(In Git Bash, prefix that command with `MSYS_NO_PATHCONV=1`, otherwise `/data/sample` is rewritten into a Windows path.) Until the reindex, search answers 503 "reindex required", because the old index was built with other models.

The UI comes from `frontend/` in live mode (`VITE_API_MODE=live`); Vite proxies `/api` to the backend:

```bash
cd frontend && npm ci && VITE_API_MODE=live npm run dev
```

Then open `http://127.0.0.1:5173`. The real-ML checks are `TEST_ML_SERVICE_URL=http://127.0.0.1:8001 uv run pytest -m ml` (from `backend/`). CI runs the same chain in the `ml-stack` job.

## Demo on the real corpus (AdiletCodex + E5)

The relevant-results demo uses real law and a real embedder:

1. Get AdiletCodex v1.0 (CC BY 4.0, 34 MB) into the git-ignored `data/raw/`:

   ```bash
   mkdir -p data/raw/adiletcodex && curl -L -o data/raw/adiletcodex/adiletcodex.csv.gz https://zenodo.org/api/records/22812626/files/adiletcodex.csv.gz/content
   ```

   Check its MD5: `bde74683987a1e52c16d339ba14953a6`.
2. Convert the Tier-1 codes (RU + KK) to the `data_schema.md` files in `data/processed/`. This gives about 9,260 articles and 16,260 chunks; add `--all-acts` for all 343 acts.

   ```bash
   cd backend && uv run python -m dev.import_adiletcodex --csv ../data/raw/adiletcodex/adiletcodex.csv.gz --out ../data/processed
   ```

3. Start the stack with the E5 ml-service. `infra/ml-e5/` adds the real embedder on top of ML's image, and the model (~1.1 GB) downloads into a volume on first start. `SEARCH_RERANK_TOP_N=0` skips ML's bootstrap word-overlap reranker, which worsens semantic results.

   ```bash
   docker compose --profile ml build ml-service
   ```

   ```bash
   ML_SERVICE_URL=http://ml-service-e5:8001 SEARCH_RERANK_TOP_N=0 docker compose --profile ml-e5 up -d --build
   ```

4. Index the corpus. On a CPU this takes about 40 minutes for 16k chunks.

   ```bash
   docker compose exec backend python -m indexer --data-dir /data/processed
   ```

The "AI answer" is still ML's extractive fallback (the first sentence of the top source). A generated answer needs an LLM (`ADILET_ML_GENERATOR_MODE=openai` with `LLM_BASE_URL`), which ML has not shipped yet.

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

Streamed answer (SSE) and feedback:

```bash
curl -N -X POST http://localhost:8000/api/v1/answer -H 'Content-Type: application/json' -d '{"query": "Ответственность работодателя за задержку зарплаты"}'
```

The stream is `sources` → `token`… → `done`, or `error` (`generation_unavailable`) after the sources if the LLM fails or times out (`ANSWER_TIMEOUT_S`). `done.text` is authoritative: citations are normalised to `[1][3]`, and invalid ones are removed and counted. Zero results give `done` with the fixed "not found" text, and the LLM is not called. A `: ping` heartbeat goes out every `SSE_PING_S`. A client disconnect cancels the upstream generation. Try the failure path with `FAKE_ML_FAIL=generate docker compose --profile dev up -d fake-ml`.

```bash
curl -X POST http://localhost:8000/api/v1/feedback -H 'Content-Type: application/json' -d '{"query_id": "<query_id from search or sources>", "target": "answer", "rating": 1}'
```

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
TEST_ML_SERVICE_URL=http://127.0.0.1:8001 uv run pytest -m ml
```

Opt-in, against the **real** ml-service. It checks the service against `contracts/ml_service.md`, then indexes ML's `data/sample/` (into the alias `test_ml_chunks`) and checks that the TOR queries find Labor Code articles in the top 5. That part is skipped until `data/sample/` exists. Run it whenever ML ships a new service or manifest.

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
  services/          search, answer (SSE), citations, feedback, fusion, snippets, lang,
                     qdrant_store, ml_client, manifest, index_info, query_log,
                     answer_store, health, background
  db/                SQLAlchemy models, session, repositories
  export_openapi.py  writes ../contracts/openapi.json
indexer/             corpus validation + indexing pipeline + CLI (python -m indexer)
migrations/          Alembic
dev/fake_ml/         fake ML service
dev/sample_corpus.py synthetic test corpus (python -m dev.sample_corpus OUT_DIR)
loadtests/           measure_search.py (single user); locust comes in BE-05
tests/               unit/, contract/, integration/
```
