# Status: Backend agent

_Last updated: 2026-10-08 · BE-03 answer (SSE), feedback, query logging (branch `be/03-answer`)_

## Current phase
BE-03: streamed RAG answer, feedback, full query logging. Code complete and tested on the fake ML and the synthetic corpus. The G1/G2 items that need ML's real sample, full Tier-1 corpus and service v0 are still open (checklists below).

## Done
- **BE-01** (PR #1) and **BE-02** (PR #2) merged; CI green on `main`.
- **`POST /answer` (SSE, sse-starlette):** reuses the search pipeline. The top `context_top_k` articles' full text goes to the generator, cut at a paragraph boundary to `max_chars_per_context`, with titles in the `data_schema.md` header format.
  - `sources` is sent at once (`ref` 1..n). Zero results → `done` with a fixed RU/KK "not found" text, `grounded: false`, `finish_reason: "no_results"`, and no LLM call.
  - `/generate` tokens are relayed as they arrive. `done` carries the authoritative text after citation cleanup and the timings `search`/`ttft`/`total`.
  - LLM error, unavailability, an incomplete stream or `ANSWER_TIMEOUT_S` → `error` (`generation_unavailable`) after the sources.
  - Client disconnect → the upstream request is closed and the answer is saved as `cancelled` (verified against the real server: a disconnect after the first token gave status `cancelled` with the partial text).
  - Heartbeat `: ping` every `SSE_PING_S` (15). Validation and search failures are plain JSON before any stream.
- **Citations** (`services/citations.py`): `[1, 3]`/`[1,3]`/`[1; 3]`/`[1][3]` → `[1][3]`. Unknown refs (`[0]`, `[12]`) are removed and counted, duplicates merged, non-numeric brackets left alone. `grounded` is false with no valid citation or a refusal phrase (phrases provisional, see Requests).
- **`POST /feedback`:** 404 for an unknown `query_id`, `article_id` required for `target=result` and ignored for `answer`, upsert on (session_hash, query_id, target, article_id), 204.
- **Full query logging:** adds `endpoint` (search/answer), `ua_family` (coarse browser/library family, never the full UA), `client` (web/api-key/unknown), `has_answer`, and `error_code` (`upstream_unavailable`, `generation_unavailable`, `cancelled`). Answer rows store sources, citations, invalid count, grounded, finish_reason, status and ttft/total/search ms. An `/answer` request is persisted once, when its stream ends (D-016). No IPs are stored.
- **Index-cache fix** (in BE-02's PR): an index built by the CLI in another process is used at once.
- CI compose smoke test now also streams an answer, checks the `done` event, posts feedback and checks the stored answer.
- Decision D-016; CHANGELOG entry 2026-10-08 (BE-03).

## Tests
229 unit (citations, answer stream with fakes: order/payloads/citations/zero results/error event/connection/incomplete/timeout/disconnect/refusal, SSE parser, UA family, heartbeat format) and 33 integration (real postgres + qdrant + fake-ml): answer streaming and persistence, KK answer, zero results, **`FAKE_ML_FAIL=generate` via a second fake-ml process → `error` after `sources`**, feedback upsert/404, plus all BE-01/02 suites.

## G1 checklist (BE-02 acceptance)
| Criterion | State |
|---|---|
| `python -m indexer --data-dir data/sample` with `--profile ml` succeeds, the alias moves | **Waiting on ML** (no `data/sample/`, no ml-service). Works on the synthetic corpus + fake ML. |
| The three TOR queries return plausible articles (top 3 here) | **Waiting on ML.** On the synthetic corpus each TOR query ranks the matching synthetic article first. |
| `/search` p50/p95 per stage, single user, 20 queries | Fake ML only: total p50 8 ms / p95 11 ms (pipeline overhead, not model cost). |

## G2 checklist (BE-03 acceptance)
| Criterion | State |
|---|---|
| With real ML v0, the three TOR queries stream answers with `[n]` citations pointing to the right sources | **Waiting on ML** (service v0 + sample). With the fake ML: the stream, citations (`[1]`), persistence and the failure paths all work. |
| Every SSE test passes; `openapi.json` documents `/answer` with the event schemas | Done. |
| The full Tier-1 corpus is indexed (counts here) | **Waiting on ML** (full corpus). The indexer is ready: `python -m indexer --data-dir /data/processed [--embeddings …]`. |
| Frontend told: answer and feedback are live, 15 s heartbeat, `done.text` replaces the streamed text | Done (below and CHANGELOG). |

## In progress
- PR for `be/03-answer`.

## Next steps
- When ML ships the sample, manifest, service v0 and full corpus: wire `ml-service`/`llm` into compose (profile `ml`), index, then paste the real TOR top 3, answers and latencies here.
- BE-04: admin API, monitoring (Prometheus/Grafana), resilience (full-text fallback, circuit breaker, cache), security (JWT, rate limits).

## Blockers (need a human)
- None for backend work. G1/G2 wait on ML (see Requests).
- **Kazakh UI text check:** the KK "not found" message in `backend/app/services/citations.py` (`NOT_FOUND_TEXT["kk"]`) needs a native speaker's review.

## Requests to other agents
| To | Request | Since | Status |
|---|---|---|---|
| ML | In `docs/status/ml.md`, paste the compose snippet for `ml-service` (port 8001) and `llm` (port 8002): image/build, env, volumes, healthcheck, resources. | 2026-10-08 | open |
| ML | Publish `data/sample/`, `ml/models/model_manifest.json` and `contracts/fixtures/fusion_cases.json` (proposed format below). | 2026-10-08 | open |
| ML | **Refusal phrases:** tell us the exact phrase(s) your prompt template makes the model use when the sources don't answer. The backend currently detects (case- and whitespace-insensitive): RU «в предоставленных источниках нет ответа», «источники не содержат ответа», «не могу ответить на основании предоставленных источников»; KK «берілген дереккөздерде жауап жоқ». The list is in `backend/app/services/citations.py`. Please use one of these or send yours. | 2026-10-08 | open |
| ML | `/generate` is called with `stream: true`, `max_tokens` 512, `temperature` 0.1, ≤ 8 sources, each text ≤ `retrieval.max_chars_per_context` (cut at a paragraph), and title `«{short_title}. Статья {N}. {title}»` / `«{short_title}. {N}-бап. {title}»`. The backend waits up to `ANSWER_TIMEOUT_S` (90 s) for each chunk and in total; tell us if CPU TTFT needs more. | 2026-10-08 | FYI |
| ML | Confirm two `data_schema.md` §8 details (CHANGELOG 2026-10-08 BE-02, D-015): timestamped collection names for same-version rebuilds; article `corpus_version` taken from the document. | 2026-10-08 | open |
| Frontend | Regenerate types. `/answer` and `/feedback` are live: the event schemas are `SourcesEvent`/`TokenEvent`/`DoneEvent`/`ErrorEvent`; replace the streamed text with `done.text`; heartbeat `: ping` every 15 s; **SSE lines end with `\r\n`** (parse `\r\n` and `\n`); a zero-result answer has `finish_reason: "no_results"`; validation/search errors before the stream are plain JSON. Confirm that `/admin/stats` covers the dashboard design. | 2026-10-08 | open |

**Proposed `fusion_cases.json` format:** `{"cases": [{"name", "mode": "hybrid|semantic|keyword", "params": {"rrf_k", "weights": {"dense", "sparse"}, "dense_limit"?, "sparse_limit"?, "rerank_top_n"?}, "dense": [chunk_id…], "sparse": [chunk_id…], "rerank_scores"?: {article_id: score}, "expected": [{"article_id", "best_chunk_id"?, "score"?}]}]}`. The backend test (`tests/unit/test_fusion.py`) runs it automatically once the file exists.

## Notes for others (endpoints, env vars, how to run)
- **API base:** `http://localhost:8000/api/v1`. CORS allows `http://localhost:5173`. Swagger UI: `/api/v1/docs`.
- **Live:** `/health`, `/version`, `/search`, `/answer` (SSE), `/feedback`, `/documents`, `/documents/{doc_id}`, `/articles/{article_id}`. **Stubs (501):** `/admin/*` (BE-04).
- **Searchable dev stack without ML data:** `docker compose --profile dev up -d --build`, then `docker compose exec backend sh -c "python -m dev.sample_corpus /tmp/sample && python -m indexer --data-dir /tmp/sample"`. Synthetic ids start with `T000000000`; the titles say they are synthetic. Don't use them as real law.
- **Answer failure drill:** `FAKE_ML_FAIL=generate docker compose --profile dev up -d fake-ml` → `/answer` sends `sources` then `error`.
- **New env vars (BE-03):** `ANSWER_TIMEOUT_S` (90), `ANSWER_MAX_TOKENS` (512), `ANSWER_TEMPERATURE` (0.1), `SSE_PING_S` (15). From BE-02: `SEARCH_*_TIMEOUT_S`, `INDEX_STATE_TTL_S`, `QDRANT_PREFER_GRPC`, `QDRANT_GRPC_PORT`.
- **Windows:** if a native PostgreSQL holds 5432, set `POSTGRES_PORT=55432` in `.env`; use `127.0.0.1`, not `localhost`, in test URLs.
- **Deployed URL:** — (BE-06).
