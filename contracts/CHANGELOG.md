# Contract changelog

Append-only, newest first. Each entry: **date · contract · version · breaking? · who must react**, then what changed and why.

Process (from `CLAUDE.md`):
1. The owner edits the contract.
2. The owner appends an entry here.
3. The owner notes it in their status file.
4. A human relays it to the affected agents.

Breaking changes need the affected owner's OK before merging.

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

Initial contracts, written during planning. Expect small additive adjustments in week 1, while the agents scaffold. After gate G0, every change follows the process above.

Open items to settle by G0:
- **Backend:** confirm that the `/answer` SSE event shapes are implementable as written with sse-starlette.
- **ML:** confirm the `text_for_embedding` header format after seeing real KK pages, and whether adilet article anchors are stable enough for `source_url`.
- **Frontend:** confirm that the `/admin/stats` fields cover the dashboard design.
