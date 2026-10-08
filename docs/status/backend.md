# Status: Backend agent

_Last updated: 2026-10-08 · real-corpus demo (branch `be/real-corpus-demo`, stacked on `be/integration`)_

## Current phase
BE-01 to BE-03 and the audit fixes are merged (PRs #1–#4). **Integration of all three parts** on the current `main` (ML commit `952d715`, Frontend PR #6): the real ml-service is wired into compose, ML's `data/sample/` is indexed with ML's models, and the frontend runs in live mode against it. Everything works end to end (details below). **Real-corpus demo** (this branch): the demo's results were unrelated to the question, so it now runs on real law and a real embedder (below). Next: BE-04.

## Real-corpus demo 2026-10-08 (branch `be/real-corpus-demo`)
**Problem (reported by a human):** in the live demo, search results and the "AI answer" had nothing to do with the question. Causes, none of them in backend code:
1. ML's `data/sample/` is 30 paraphrased Labor Code fragments, so most questions have no relevant article at all.
2. The ml-service embedder is a hash function (`hash-bm25-ch1`), not a model: "similar" means "shares hashed tokens".
3. The reranker scores word overlap and reorders the semantic results by it.
4. The answer generator is extractive: the first sentence of the top source. It can only be as relevant as source [1].

**What Backend changed (all in backend-owned paths):**
- `dev/import_adiletcodex.py`: converts the public AdiletCodex v1.0 corpus (CC BY 4.0, Zenodo 10.5281/zenodo.22812626; parsed from adilet.zan.kz) into the `data_schema.md` Parquet files. Tier-1 acts from `ml/configs/corpus.yaml`, RU + KK, text verbatim, footnotes → `amendment_notes`, §5 headers, RU↔KK links. Output: 16 documents, 9,259 articles, 16,264 chunks (9,248 linked across languages). It passes the indexer's validator. The data goes to git-ignored `data/raw/` and `data/processed/`.
- `article_id` / `doc_id` accept `_`: real adilet codes end in one (`K030000442_`). See CHANGELOG.
- `infra/ml-e5/`: an overlay on ML's image with `sentence-transformers` + `intfloat/multilingual-e5-base` (pinned torch CPU / sentence-transformers / transformers). Its manifest is derived from ML's (`pipeline_version` `…-e5`, `index_compat_id` `e5base-…`), so an index built with the hash embedder is refused. Compose service `ml-service-e5`, profile `ml-e5`.
- `SEARCH_RERANK_TOP_N` (env): overrides the manifest's rerank depth; `0` turns the rerank stage off. The demo uses 0 until ML ships a real cross-encoder.
- `backend/README.md`: "Demo on the real corpus".

- **Generated answers:** ML's `openai` generator mode works with a hosted OpenAI-compatible LLM. Groq was checked with `qwen/qwen3.8-27b`, a plain-text answer with `[1]` in RU and KK in about 1.3 s; `openai/gpt-oss-120b` also works but writes Markdown bold. Configure it in `.env` (README, step 5). The local `llm` compose service is still an empty placeholder (ML).
- **Indexer recovery:** a Docker crash mid-index left the job `running` and blocked every later run. `python -m indexer … --abandon-stuck-job` fails such a job and deletes its partial collection (tests included).

## Integration 2026-10-08 (main @ 952d715)
Run on the dev laptop (i7-13700HX, Docker Desktop/WSL2).

| Check | Result |
|---|---|
| Backend unit + contract tests | 248 passed. **ML's `contracts/fixtures/fusion_cases.json`: all 7 cases pass against the backend's fusion** (offline and online ranking agree, D-005). |
| ML's own tests (`ml/`, `pytest`) | 30 passed (3 deprecation warnings). |
| `data/sample/` against `data_schema.md` (indexer validator) | valid: 2 documents, 30 articles, 33 chunks, `corpus_version` 2026.10.08-bootstrap |
| `docker compose --profile ml` with `ML_SERVICE_URL=http://ml-service:8001` | healthy; `/health` ok, `pipeline_version` 0.1.0-bootstrap |
| Search on the old index built with the fake models | 503 "reindex required" (the `index_compat_id` check works: fake ≠ hash-bm25-ch1) |
| `python -m indexer --data-dir /data/sample` (ML's service, `MANIFEST_SOURCE=service`) | 33 points → `legal_chunks__0.1.0-bootstrap`, alias switched, synthetic rows pruned, 5.1 s |
| `pytest -m ml` (real-ML contract + TOR tests) | **6 passed** |
| `/answer` via ML's fallback generator | `sources` → 17 `token` → `done`, citations `[1]`, grounded |
| KK search; RU↔KK / prev / next article links | KK query → `K1500000414:kk:a114` first; links resolve |
| Frontend: `npm ci`, `gen:api` (no drift), lint, 12 unit tests, production build | all pass |
| Frontend live mode (Vite proxy → backend) in a browser | search shows 10 results (`a114` first); "Сформировать ответ" streams the cited answer with sources [1]–[5]; no console errors |

**TOR queries (ML bootstrap models: hash embedder + lexical reranker, ML's bootstrap Labor Code sample, NOT real model quality):**
1. «Ответственность работодателя за задержку зарплаты» → 1. `K1500000414:ru:a114` (ответственность за задержку зарплаты), 2. `a96`, 3. `a52`.
2. «Штраф за нарушение экологических норм» → Labor Code articles only (`a114`, `a96`, `a23`): the sample has no Environmental Code, so nothing relevant can be found yet.
3. «Основания расторжения трудового договора» → 1. `K1500000414:ru:a52` (основания расторжения), 2. `a96`, 3. `a33`.

**Latency, single user, 60 requests (3 × 20 queries), ML bootstrap models, 33-chunk index:** embed p50/p95 2/3 ms, retrieve 3/8, fuse 0/0, rerank 2/3, total 11/16 ms, client wall 14/20 ms. These are not real-model numbers: E5 + cross-encoder latency will be measured when ML pins them.

## Findings for the other parts (not fixed by Backend; not their code)
| Part | Finding | Why it matters |
|---|---|---|
| ML | `data/sample/` texts are paraphrased teaching fragments, but they sit under the **real** Labor Code id `K1500000414`, real article numbers and real `adilet.zan.kz` links. The "(bootstrap sample)" marker is only in `documents.title`; `short_title` and the article titles carry none, so the UI shows «Трудовой кодекс РК · Статья 114 · Действует» with non-official text. | CLAUDE.md: legal text is shown verbatim. Fine for integration, but **not for demos or screenshots** until the real scrape replaces it. Suggest a marker in `short_title` (e.g. «Трудовой кодекс РК (учебный образец)») until then. |
| ML | The ml-service models are still bootstrap (hash embedder, lexical reranker, extractive fallback), and the manifest revisions say `to-pin-after-fetch`. | G1 asks for "real zero-shot models" and real latency; not met until E5 and the cross-encoder are pinned. |
| ML | `ml/` has no lockfile (`uv.lock`), `serving/Dockerfile` uses an unpinned `python:3.12-slim` and `pip install .` with open ranges. | CLAUDE.md reproducibility rule (pin versions). |
| ML | ML's engine appends `/v1/chat/completions` to `LLM_BASE_URL`, so the base must not end in `/v1` (Backend's `.env.example` is now aligned). OpenAI-style hosted endpoints are usually given **with** `/v1`. | Document it in `ml/serving/README.md`, or strip a trailing `/v1`, so switching to a GPU endpoint on demo day is not a trap. |
| ML | Article `source_url` anchors are `#a{N}` (e.g. `…/K1500000414#a114`). | Check that adilet really has such anchors; otherwise links open the document top (acceptable, but then say so). |
| ML | `FastAPI.on_event` deprecation warnings in ml-service. | Minor; move to `lifespan`. |
| Frontend | Live integration (search, streamed answer, sources, citations) now **verified** against the real backend + ML service. The status file still says "unverified". | Update the status file. |
| Frontend | Result cards show `doc.short_title`, so the bootstrap/non-official nature of ML's sample text is invisible (see the first ML row). | No action needed if ML marks `short_title`; otherwise consider showing a "sample data" badge when `pipeline_version` ends in `-bootstrap`. |

## Done
- **BE-01 to BE-03 + audit fixes** merged (PRs #1–#4): skeleton, indexer, hybrid search, documents/articles, streamed answer (SSE), feedback, query logging, stage budgets, ML limit guards, opt-in real-ML tests.
- **Integration (this branch):**
  - `ml-service` is wired into `docker-compose.yml` from ML's snippet, under profile `ml`. The port is bound to 127.0.0.1, a model-cache volume is added, and the `llm` placeholder moves to its own profile `llm-cpu` so `--profile ml` does not pull a llama.cpp image that ML's fallback generator does not use.
  - New CI job **`ml-stack`**: builds ML's image, starts the stack on the real ml-service, indexes `data/sample`, checks search (TOR → Labor Code) and an answer stream, and runs `pytest -m ml`. The backend workflow now also triggers on `ml/**` and `data/sample/**`, so an ML change that breaks the integration fails CI.
  - `.env.example`: `ML_SERVICE_PORT`, `ADILET_ML_EMBEDDER_BACKEND`, `ADILET_ML_GENERATOR_MODE`; `LLM_BASE_URL` without `/v1` (ML appends it).
  - `backend/README.md`: "Run the whole project".

## G1 checklist (BE-02 acceptance)
| Criterion | State |
|---|---|
| `python -m indexer --data-dir data/sample` with `--profile ml` succeeds, the alias moves | **Done** (ML's bootstrap sample + bootstrap models). |
| The three TOR queries return plausible articles (top 3 here) | **Partly:** wage delay and termination → the right Labor Code article first; ecology → nothing relevant (no Environmental Code in the sample). On bootstrap models and bootstrap text, see above. |
| `/search` p50/p95 per stage, single user, 20 queries | Measured on ML's bootstrap models (above). **Real-model numbers pending** (E5 + cross-encoder not pinned yet). |

## G2 checklist (BE-03 acceptance)
| Criterion | State |
|---|---|
| With real ML v0, the TOR queries stream answers with `[n]` citations pointing to the right sources | **Done on ML's bootstrap service** (extractive fallback generator): `[1]` → `K1500000414:ru:a114`. An LLM-generated answer is pending ML's generator. |
| Every SSE test passes; `openapi.json` documents `/answer` with the event schemas | Done. |
| The full Tier-1 corpus is indexed (counts here) | **Waiting on ML** (real scrape of the full corpus). |
| Frontend told | Done; Frontend's UI consumes the stream correctly (verified live). |

## Next steps
- BE-04: admin API, monitoring (Prometheus/Grafana), resilience (full-text fallback, circuit breaker, cache), security (JWT, rate limits).
- From Frontend's status (2026-10-08), for BE-04:
  1. tell "citation refers to a valid source" apart from "the source supports the claim";
  2. catch refusals phrased outside `REFUSAL_PHRASES` (a VAT answer that says the sources don't cover it was marked grounded), with the wording agreed with ML's prompt template;
  3. expose the upstream generator failure reason safely.
- When ML pins real models / ships the real corpus: reindex (`--embeddings` if precomputed), re-run `pytest -m ml` and `loadtests/measure_search.py`, and update the TOR results and latencies here.

## Blockers (need a human)
- None for backend work.
- **Kazakh UI text check:** `NOT_FOUND_TEXT["kk"]` in `backend/app/services/citations.py` needs a native speaker's review.

## Requests to other agents
| To | Request | Since | Status |
|---|---|---|---|
| ML | Compose snippet for `ml-service` | 2026-10-08 | **done** (wired, profile `ml`) |
| ML | `data/sample/`, `model_manifest.json`, `fusion_cases.json` | 2026-10-08 | **done** (all 7 fusion cases pass on the backend) |
| ML | Refusal phrases | 2026-10-08 | **done** (RU «В предоставленных источниках нет ответа.», KK «Берілген дереккөздерде жауап жоқ.»; both are detected by `citations.py`) |
| ML | Confirm D-015 details | 2026-10-08 | **done** (CHANGELOG 2026-10-08, ML) |
| ML | Run `pytest -m ml` after each ml-service/manifest change | 2026-10-08 | ongoing; CI's `ml-stack` job now does it on every PR touching `ml/` |
| ML | See "Findings for the other parts": mark the bootstrap sample, pin models + lockfile, `LLM_BASE_URL` convention, adilet anchors. A `llm` compose snippet is still needed when the GGUF generator is ready (profile `llm-cpu`). | 2026-10-08 | open |
| ML | Real-corpus demo: adopt or replace `backend/dev/import_adiletcodex.py` (AdiletCodex → `data_schema`) until the ML-01 scraper ships; make E5 the default embedder in ML's own image (then `infra/ml-e5/` can go); a real cross-encoder (the word-overlap reranker hurts semantic results, so the demo runs with `SEARCH_RERANK_TOP_N=0`); stemming for the sparse encoder; an LLM generator. Note: real `source_url` anchors are adilet's own (`#z104`), not `#a{N}`. | 2026-10-08 | open |
| Frontend | Live integration verified by Backend (see Integration); update your status. Consider a "sample data" badge while `pipeline_version` ends in `-bootstrap`. Confirm that `/admin/stats` covers the dashboard design before BE-04. | 2026-10-08 | open |

## Notes for others (endpoints, env vars, how to run)
- **Whole project:** `docker compose --profile dev stop fake-ml`, then `ML_SERVICE_URL=http://ml-service:8001 docker compose --profile ml up -d --build`, then `docker compose exec backend python -m indexer --data-dir /data/sample`, then `cd frontend && npm ci && VITE_API_MODE=live npm run dev` → `http://127.0.0.1:5173`. See `backend/README.md` (PowerShell and Git Bash notes there).
- **API base:** `http://localhost:8000/api/v1`. CORS allows `http://localhost:5173`. Swagger UI: `/api/v1/docs`.
- **Live:** `/health`, `/version`, `/search`, `/answer` (SSE), `/feedback`, `/documents`, `/documents/{doc_id}`, `/articles/{article_id}`. **Stubs (501):** `/admin/*` (BE-04).
- **Fake stack (no ML):** `docker compose --profile dev up -d --build` + the synthetic corpus (`python -m dev.sample_corpus /tmp/sample && python -m indexer --data-dir /tmp/sample`). Synthetic ids start with `T000000000`; don't use them as real law.
- **Switching models** (fake → ML bootstrap → real E5): each needs a reindex. Until then search answers 503 "reindex required" (by design).
- **Env vars:** `ML_SERVICE_PORT`, `ADILET_ML_EMBEDDER_BACKEND`, `ADILET_ML_GENERATOR_MODE` (new); `ANSWER_*`, `SSE_PING_S`, `SEARCH_*_TIMEOUT_S`, `INDEX_STATE_TTL_S`, `QDRANT_PREFER_GRPC`, `QDRANT_GRPC_PORT`.
- **Windows:** if a native PostgreSQL holds 5432, set `POSTGRES_PORT=55432` in `.env`; use `127.0.0.1`, not `localhost`, in test URLs; in Git Bash prefix container paths with `MSYS_NO_PATHCONV=1`.
- **Deployed URL:** — (BE-06).
