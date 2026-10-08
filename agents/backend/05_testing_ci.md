# BE-05: Testing, CI, load test (week 5)

**Goal: G4.** The test suites are green in CI, and a load test proves `/search` p95 ≤ 2 s with the v1.0.0 models.

## Tasks

1. **Close coverage gaps.** Keep coverage of `app/services` and `app/api` ≥ 80% (pytest-cov, report in CI). Add the missing edge cases: empty filters, `top_k` boundaries, the KK path, very long queries (422), Unicode normalisation, and concurrent feedback upserts.

2. **Contract tests.**
   - Run **schemathesis** against the running app using `contracts/openapi.json` (stateless checks: status codes are documented, responses conform to the schema, no 500s).
   - Exclude the SSE endpoint from schemathesis; it is covered by the dedicated SSE tests.
   - Add a test that **every** example JSON block in `contracts/api.md` validates against the corresponding Pydantic model.

3. **Migration test:** upgrade to head, downgrade to base, upgrade again, on a clean Postgres in CI.

4. **Reindex with v1.0.0** as soon as ML announces it:
   - use the precomputed embeddings;
   - build a new collection and switch the alias;
   - keep the previous collection for rollback;
   - record the duration and counts.

5. **Load test** (`backend/loadtests/locustfile.py`).
   - Query mix: gold queries exported by ML (no labels needed), 80% `/search` hybrid, 10% `keyword`, 10% `/answer` (tracked separately).
   - Scenarios, run on hardware like the deployment target (4 vCPU; real `ml-service` v1.0.0 on CPU):
     - warm-up 1 min;
     - 10 concurrent users for 5 min;
     - 25 concurrent users for 5 min.
   - Report p50/p95/p99, RPS, error rate and the per-stage breakdown from Prometheus, in `docs/report/load_test.md`, with charts and the hardware description.
   - **If p95 > 2 s**, find the bottleneck from the stage metrics and fix it, in this order:
     1. uvicorn/gunicorn worker count;
     2. connection pooling;
     3. the cache;
     4. lowering `rerank_top_n` via env (tell ML about the quality cost);
     5. asking ML for the ONNX/int8 reranker.

     Re-run after each fix and keep the before/after table.

6. **CI** (`.github/workflows/`):
   - **backend:** ruff, mypy, unit tests, integration tests (service containers: postgres, qdrant, fake-ml), schemathesis, the openapi drift check, `pip-audit`, the docker build.
   - **ml and frontend jobs:** ask the owners for their exact commands (status-file requests), then add their jobs (ML: ruff + unit tests without models; Frontend: lint, typecheck, unit tests, build, Playwright against MSW).
   - Cache uv and npm downloads. The full pipeline should finish in < 15 min.
   - Optionally build and push images to GHCR on pushes to `main`.

7. **Smoke script** `scripts/smoke.sh <base_url>`: health, one search per language, one answer (expect a `done` event), one article fetch, the admin login rejecting bad credentials. It is used after every deployment.

## Acceptance criteria (G4)

- [ ] CI is green on `main` for backend, ml and frontend.
- [ ] `docs/report/load_test.md` shows `/search` p95 ≤ 2 s at 10 concurrent users on the target-like hardware, or states clearly what remains and the plan to fix it.
- [ ] Pipeline v1.0.0 is indexed in the dev/staging stack, and `/admin/system` shows `compatible: true`.
