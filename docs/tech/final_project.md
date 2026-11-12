# Final project: running and validating the prototype

The assignment screenshot in `../Final Project/image.png` asks for a working prototype with a
model, API, UI, testing, monitoring, technical documentation and a 7–10 slide presentation.
Submission is due **23 November 2026 at 00:00**, as shown in Moodle.

The screenshot is outside this Git repository, in the sibling `Final Project` folder.

## Start locally (PowerShell 7, Docker Desktop)

From the repository root:

```powershell
./infra/start-final.ps1 -Index -Corpus sample
```

This creates an ignored `.env.final` with local ports and generated monitoring/session secrets.
It starts the isolated `adilet-final` project and indexes the committed official Labor Code.
Existing Docker projects and their data are retained. First startup downloads model weights.
On first creation, the script records a CPU demo preset: 4 inference workers, 1 OpenMP/MKL thread
per call, and reranking of the first 3 fused candidates. Optional `-InferenceWorkers`, `-CpuThreads`
and `-RerankCandidates` parameters change that initial preset. An existing `.env.final` is preserved;
edit its values explicitly to retune a running deployment. The preset is a measured laptop
tradeoff and does not prove the two-second target on another machine or corpus.
Use `-Index` only when building or replacing the index; without it, the saved index is reused.
Do not recreate the backend or ML container while an indexing process is running inside it.

For the larger corpus, prepare the data first:

```bash
cd ml
uv sync --frozen --extra dev --python 3.12
uv run --frozen python scripts/download_data.py
```

Then run `./infra/start-final.ps1 -Index -Corpus processed` from the repository root. Indexing
16,264 chunks with CPU E5 is substantially slower than indexing the 805-chunk sample.

| Component | Local URL |
|---|---|
| Production UI, live API proxy | http://127.0.0.1:18080 |
| Swagger | http://127.0.0.1:18000/api/v1/docs |
| Backend health | http://127.0.0.1:18000/api/v1/health |
| ML health | http://127.0.0.1:18001/health |
| Prometheus targets | http://127.0.0.1:19090/targets |
| Grafana | http://127.0.0.1:13000 |

Grafana uses `admin` and the password in `.env.final`. Prometheus scrapes both the backend and ML
service. The provisioned dashboard shows service availability, traffic, HTTP errors, search p95
and ML latency. It does not implement the planned application admin panel: `/api/v1/admin/*`
now includes the teammate implementation merged from `main`; earlier runtime evidence
predates that merge. Configure admin credentials and rehearse it before demonstrating it.

## Model and data identity

`ml/models/model_manifest.json` records pipeline `0.2.0`, pinned E5 and cross-encoder revisions,
768-dimensional cosine vectors, query/passage prefixes, BM25 parameters and RRF configuration.
`index_compat_id=e5base-bm25st-ch1` must match the index. Reindex after changing it.

The runtime may override reranking depth with `SEARCH_RERANK_TOP_N`. This changes ranking
behaviour without changing embeddings, so it needs a new retrieval check but not a reindex.
`ADILET_ML_INFERENCE_WORKERS` bounds parallel model calls and `ADILET_ML_CPU_THREADS` sets
OpenMP/MKL threads through Compose. Inference runs off the ASGI event loop so health checks
remain responsive. Record these three settings with each load result. A smaller candidate pool
trades reranking coverage for CPU latency; do not imply it is identical to the manifest's 20.

The models are pretrained; project-specific fine-tuning and a fair winning-model comparison are
not evidenced by the current experiment folder. The available baseline is BM25 on 1,318 held-out
title queries against article bodies, not a human-labelled natural-language benchmark.

The full imported snapshot has 16 document-language records, 9,259 article-language records and
16,264 chunks. The default sample contains only the official Labor Code. Do not demonstrate an
ecology question against the sample and imply that the full corpus is indexed.

## Generated answers

The default is explicitly **extractive fallback**, requiring no external key. For an actual LLM,
edit `.env.final` locally and set `ADILET_ML_GENERATOR_MODE=openai`, `LLM_BASE_URL`, `LLM_MODEL`, and
`LLM_API_KEY`, then rerun the startup script without `-Index`. The base URL excludes `/v1`.
The key remains server-side. Record the actual served generator model separately from the
retrieval manifest; an unspecified generator is not a reproducible final model.

The current local final stack has reused the existing server-side Groq configuration for
`openai/gpt-oss-120b`. RU/KK answers were checked end to end for the working-hours example;
the exact text and timing are in `docs/report/final_smoke.json`. A fresh checkout still defaults
to fallback. Never include `.env.final` or `.env.localtest` in the submission archive.

## Validation

```bash
cd ml
uv run --frozen --extra dev pytest -q
uv run --frozen --extra dev ruff check src tests scripts
```

```bash
cd backend
uv run --frozen pytest -q
uv run --frozen ruff check app tests
uv run --frozen python -m app.export_openapi --check
```

```bash
cd frontend
npm ci
npm run build
npm test
npm run lint
npm run test:e2e
```

Unit tests do not establish live deployment, retrieval quality or latency. Record end-to-end
requests and non-degraded results separately. For sequential latency, from `backend`:

```bash
uv run --frozen python loadtests/measure_search.py --base-url http://127.0.0.1:18000 --rounds 2 --top 3
```

The project's p95 ≤2 s target is for 10 concurrent users. A sequential run alone does not prove
that target. See `docs/report/final_readiness.md` for measured checks and remaining gaps.

## Presentation

`docs/presentation/final_deck.pptx` is editable and contains 10 slides with speaker notes and
local source references. `final_deck.md` is the text version. Copies for submission live beside
the assignment screenshot in `Group Project/Final Project/`. The deck is marked **evidence
draft** until runtime, model-selection and deployment measurements are complete.

Rebuild with `python docs/presentation/build_final.py` in an environment with `python-pptx`.
Export PDF through PowerPoint or LibreOffice and visually inspect the rendered output.

## Stop while retaining data

```bash
docker compose -p adilet-final --env-file .env.final -f docker-compose.yml -f docker-compose.final.yml --profile ml stop
```

All published ports bind to loopback. Public HTTPS hosting requires a reachable host and domain
or an approved tunnel. The local URL is not a public deployment claim.
