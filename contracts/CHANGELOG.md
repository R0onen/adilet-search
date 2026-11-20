# Contract changelog

Append-only, newest first. Each entry: **date · contract · version · breaking? · who must react**, then what changed and why.

Breaking changes need the affected component owner's OK before merging.

---

## 2026-11-12 · api.md, openapi.json · v1 · no (one behaviour change, see below) · Frontend (regenerate types)

Backend phase BE-04. Every `/admin/*` endpoint is live; their `501` responses are removed from `openapi.json`.
- **Auth:** `POST /admin/login` returns a JWT (8 h). All other admin routes answer `401` without a valid `Authorization: Bearer` token. Login is limited to 5/min.
- **Rate limits are enforced:** `/search` 60/min and `/answer` 10/min per session + IP; `429` with `Retry-After` in seconds. Show the user a "try again in N s" message.
- **Behaviour change, `/search` and `/answer`:** when the ML service, Qdrant or the index is unavailable, the response is now `200` with `degraded: ["semantic"]` and results of `score_type: "fts"` (Postgres full-text fallback) instead of `503`. `503` remains only for "the fallback failed too". The UI should show a notice when `degraded` is not empty.
- **New error:** `413 content_too_large` for bodies over 64 KB.
- **`/admin/stats`:** days are UTC days, both bounds inclusive, at most 366 days. `by_day` lists every day of the range, with `queries: 0` and `null` rates for empty days.
- **`/admin/queries`:** `q` is a case-insensitive substring of the normalised query. Newest first.
- **`/admin/reindex`:** `422` if the chosen corpus is not on the server; `409` while a job runs. Poll `/admin/jobs/{id}`; a failed job's `message` holds the error.
- **`/metrics`** (Prometheus) is served at the root path of the backend; it is not part of the public API.

---

## 2026-11-11 · model manifest (ml_service.md unchanged) · pipeline 0.2.0 · no (reindex required) · Backend

ML pipeline `0.2.0`. No endpoint or schema changed; the manifest content did:
- `index_compat_id` is now `e5base-bm25st-ch1` (real E5 embedder; sparse tokens are stemmed for Russian). Existing indexes are refused until `python -m indexer` is run again.
- `embedder.runtime` / `reranker.runtime` select the implementation (`sentence-transformers` / `cross-encoder`, or the offline `hash` / `lexical`). Both models have pinned revisions.
- `retrieval.rerank_top_n` is 20 (was 30), to fit the cross-encoder into the latency budget on CPU.
- `ml/models/model_manifest.bootstrap.json` is the offline variant for tests and CI (`index_compat_id` `hash-bm25st-ch1`).
- `data/sample/` is now the complete official Labor Code; `corpus_version` is `2026.09.17`. `data/sample/sample_articles.json` is removed.

---

## 2026-10-08 · openapi.json (api.md unchanged) · v1 · no · Frontend (regenerate types), ML (FYI)

Real adilet document codes can end in an underscore (e.g. `K940001000_`, the Civil Code, General Part; `K030000442_`, the Land Code). The backend's `article_id` pattern rejected them, which `data_schema.md` §2 never required. The pattern is now `^[A-Za-z0-9_]+:(ru|kk):[a-z0-9-]+$`, and the indexer accepts such `doc_id`s. This is a relaxation, so nothing that was valid becomes invalid.

**For ML (FYI):** until the ML-01 scraper ships, `backend/dev/import_adiletcodex.py` converts the public AdiletCodex v1.0 corpus (CC BY 4.0, Zenodo 10.5281/zenodo.22812626, parsed from adilet.zan.kz) into the `data_schema.md` Parquet files. It covers RU + KK, the Tier-1 acts from `ml/configs/corpus.yaml`, keeps the text verbatim, moves footnotes to `amendment_notes`, and uses the §5 header format. ML may adopt it into `ml/` or replace it.

---

## 2026-10-08 · fixtures/fusion_cases.json, ml_service.md · v1 · no · Backend

ML phase bootstrap. Added `contracts/fixtures/fusion_cases.json` with the weighted-RRF cases from
`ml_service.md` §2: ties, chunks present in one list, article collapse, unequal weights, empty
lists, keyword mode and rerank head reordering. This is additive and lets Backend compare its
fusion implementation against ML's implementation.

ML also confirms the BE-02 indexing details from the 2026-10-08 changelog:
- same-version rebuilds may use timestamped collection names;
- `articles.parquet` has no `corpus_version`, so Backend should derive it from the document row.

---

## 2026-10-08 · api.md, openapi.json · v1 · no · Frontend (regenerate types), ML (FYI)

Backend phase BE-03. `POST /answer` (SSE) and `POST /feedback` are live; their `501` responses are removed from `openapi.json`. Clarifications in `api.md` (additive):
- **Zero results:** `done.finish_reason` is `"no_results"`.
- **Line endings:** SSE lines may end with `\r\n` (sse-starlette's default) or `\n`; clients must accept both.
- **Errors before the stream:** validation (422) and search failures (503) are plain JSON, no stream is opened.
- **`/feedback`:** for `target: "answer"`, `article_id` is ignored; an unknown `query_id` returns 404.

The `error` event message for a failed generation is "The answer generator is unavailable; the sources above are valid." (code `generation_unavailable`).

---

## 2026-10-08 · openapi.json (api.md unchanged) · v1 · no · Frontend (regenerate types)

Backend phase BE-02. `POST /search`, `GET /documents`, `GET /documents/{doc_id}` and `GET /articles/{article_id}` are now live. Their `501` responses are removed from `openapi.json`. `/search` documents `503 upstream_unavailable` (no index yet, ML or Qdrant down, or an incompatible index; the full-text fallback replaces this in BE-04).
- **`SearchTiming`** (`timing_ms`): each key is now an optional integer instead of a nullable one. A stage that did not run is omitted (e.g. no `rerank` in `keyword` mode), exactly as `api.md` says ("a `timing_ms` key may be missing"). In TypeScript: `rerank?: number` instead of `rerank?: number | null`.

**For ML (`data_schema.md` §8, owned jointly), implemented by Backend; please confirm or object:**
- When `legal_chunks__{pipeline_version}` already exists (a corpus rebuild with the same models), the indexer builds `legal_chunks__{pipeline_version}__{YYYYMMDDHHMMSS}` next to it and then switches the alias. Existing collections are never deleted automatically; they stay for rollback.
- `articles.parquet` has no `corpus_version` column (§4); the backend stores the document's `corpus_version` on each article row.

---

## 2026-10-08 · api.md, openapi.json · v1 · no · Frontend (regenerate types), ML (FYI)

Backend phase BE-01. `contracts/openapi.json` is generated for the first time and lists all 16 v1 endpoints with their real models. Every endpoint except `/health` and `/version` is a stub that returns `501`. All `api.md` changes are additive or clarifications:
- **Error codes:** added `not_implemented` (501, stubs during development only). Other HTTP error statuses use a code derived from the reason phrase (e.g. `method_not_allowed` for 405). `validation_error.details` is a list of `{loc, msg, type}`.
- **Request id:** a client-sent `X-Request-Id` is echoed if it is 8–128 chars of `[A-Za-z0-9._-]`; otherwise the server generates one.
- **`/health`:** component values are `ok | degraded | down | unavailable`. `status` is `down` iff the database is not ok, `degraded` if qdrant or ml_service is not ok; `llm` is reported but does not change `status` (this matches the existing example). `pipeline_version` (here and in `/version`) is `null` until the manifest is loaded. `/version.index_collection` is `null` before the first index.
- **`/documents/{doc_id}`:** `lang` is required; unknown (`doc_id`, `lang`) → 404.
- **`/answer` SSE:** the event payloads are published in `openapi.json` as `SourcesEvent`, `TokenEvent`, `DoneEvent`, `ErrorEvent`, linked from the 200 response under `x-sse-events`. Confirms the open G0 item: the event shapes are implementable as written.
- **Examples:** ids and timestamps that were `"…"` are now concrete values (UUIDs, ISO timestamps). A backend test checks that every example in `api.md` validates against the models and round-trips.
- **IDs in requests:** `article_id` must match `{doc_id}:{ru|kk}:{unit_key}`; `query_id`, `answer_id` and `job_id` are UUIDs.

---

## 2026-10-05 · api.md, ml_service.md, data_schema.md · v1 · — · everyone

Initial contracts, written during planning. Expect small additive adjustments in week 1, while the components are scaffolded.

Open items to settle by G0:
- **Backend:** confirm that the `/answer` SSE event shapes are implementable as written with sse-starlette.
- **ML:** confirm the `text_for_embedding` header format after seeing real KK pages, and whether adilet article anchors are stable enough for `source_url`.
- **Frontend:** confirm that the `/admin/stats` fields cover the dashboard design.


## 2026-11-12 — Final prototype citation formatting
- Backend accepts numeric references emitted in Unicode brackets (`【1】`, `［1］`) and
  normalises them to the existing canonical `[1]` output before validating source IDs.
- Why: generated answers could otherwise show non-clickable citations despite referring to a
  supplied source. Non-numeric bracketed text and stored legal source text remain unchanged.
- Breaking: no. Public response schemas and citation reference semantics are unchanged.
- Frontend: no type changes required; existing canonical citation rendering handles the output.

## 2026-11-14 — Reranker depth and input length in the manifest
- `ml/models/model_manifest.json`: `retrieval.rerank_top_n` is 5 (was 20) and `reranker.max_seq_len` is 256 (was 384).
- Why: with 20 candidates the reranker could not serve 10 concurrent users on CPU (97% of hybrid searches were returned without reranking). With 5 candidates p95 is 0.88 s uncached, and "right article first" on the synthetic test questions is 83.1% against 85.6% (72.8% without a reranker). See `docs/report/load_test.md`.
- Breaking: no. `index_compat_id` is unchanged, so no reindex is needed. `SEARCH_RERANK_TOP_N` still overrides the manifest.
- Who must react: nobody. Reports that quote ranking quality should state the rerank depth they were measured with.

## 2026-11-15 — Answer prompt: no bare refusal when there is no direct answer
- `ml/prompts/answer_v1.md`: when the sources do not directly answer, the model now opens with a fixed sentence (`В найденных статьях нет прямого ответа на этот вопрос.` / `Табылған баптарда бұл сұраққа тікелей жауап жоқ.`), then says what the related sources do establish (with citations) and what kind of rule is missing. It still may not state rules that are not in the sources.
- Backend: the new opening sentences are recognised as a refusal, so such answers keep `grounded: false` while their citations stay clickable. The old sentences are still recognised.
- Why: a one-line "no answer in the sources" was a dead end for questions outside the indexed codes.
- Breaking: no. Event shapes are unchanged.

## 2026-11-15 — `/generate` source texts: a total budget, and the matched passage for long articles
- Backend: the source texts of one answer together are at most `ANSWER_MAX_CONTEXT_CHARS` (default 10,000 characters; per source still at most `max_chars_per_context`). A source is the whole article when it fits its share, otherwise the retrieved passage of the article instead of the article's beginning.
- `contracts/ml_service.md`: the description of `sources[].text` says so. The request shape is unchanged.
- ML service: on HTTP 429 from the LLM provider with a `retry-after` of at most 30 s, `/generate` waits and retries once before reporting `llm_unavailable`.
- `ml/prompts/answer_v1.md`: the "no direct answer" opening is used only when no source states the rule asked about; an answer that depends on conditions listed in the sources is a direct answer.
- Why: with five long articles a request exceeded the provider's tokens-per-minute limit and 4 of 30 test answers failed every time; the model also opened 9 of 13 answers with "no direct answer" although the cited article answered the question.
- Breaking: no.
- Who must react: nobody.

## 2026-11-16 — Pipeline 1.0.0 is the default manifest
- `ml/models/model_manifest.json` is now pipeline `1.0.0`: the reranker is our fine-tuned cross-encoder, published as `qb2k/adilet-reranker-mminilm-ru-kk` on the Hugging Face Hub and pinned by revision. `model_manifest.pretrained.json` is the former default (`0.2.0`); `model_manifest.ft.json` (local checkpoint) is removed.
- The ML service runs one embed and one rerank call at startup, so the first user request is not slow.
- Breaking: no. `index_compat_id` is unchanged, so no reindex is needed. The first start downloads 470 MB more.
- Who must react: deployments that set `ML_MODEL_MANIFEST_PATH=/app/models/model_manifest.ft.json` must remove the variable.
