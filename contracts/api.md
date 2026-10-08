# Public API contract (v1)

- **Owner:** Backend.
- **Consumers:** Frontend, the Legal Service backend (integration), ML (`eval_api.py`).
- **Base path:** `/api/v1`. Bodies are JSON in UTF-8. Timestamps are ISO 8601 UTC; dates are `YYYY-MM-DD`.

This document is normative for the shapes and the meaning of the API. `contracts/openapi.json` is generated from the backend code and must match it. All example values are illustrative, but every example in this file validates against the backend models (a backend test checks this).

The running backend also serves its schema at `/api/v1/openapi.json` and Swagger UI at `/api/v1/docs`.

---

## 1. Conventions

- **Languages:** `ru` and `kk`.
- **IDs** (see `data_schema.md` §2):
  - `doc_id` is the adilet code, e.g. `K1500000414`.
  - `article_id` = `{doc_id}:{lang}:{unit_key}`, e.g. `K1500000414:ru:a113`.
  - `chunk_id` = `{article_id}:c{n}`.
- **Session:** the optional header `X-Session-Id` carries a random UUID that the client generates and keeps in localStorage. It is anonymous, and the server stores only a salted hash of it.
- **Request id:** every response carries an `X-Request-Id` header. A client may send its own `X-Request-Id` (8–128 chars of `[A-Za-z0-9._-]`); it is echoed back and appears in the server logs. Otherwise the server generates one.
- **Errors** (every non-2xx response, except inside an SSE stream):
  ```json
  {"error": {"code": "validation_error", "message": "Query must be 1–500 characters", "details": null, "request_id": "9b2e…"}}
  ```

  | code | HTTP |
  |---|---|
  | `validation_error` | 422 |
  | `unauthorized` | 401 |
  | `forbidden` | 403 |
  | `not_found` | 404 |
  | `conflict` | 409 |
  | `rate_limited` | 429 (with a `Retry-After` header) |
  | `internal_error` | 500 |
  | `upstream_unavailable` | 503 |
  | `not_implemented` | 501 (only while an endpoint is still a stub during development) |

  Any other HTTP error status uses a code derived from its reason phrase, e.g. `method_not_allowed` for 405.
  For `validation_error`, `details` is a list of `{"loc": [...], "msg": "…", "type": "…"}`, one per invalid field.

- **Pagination:** `?page=1&page_size=20` (`page_size` max 100) returns `{"items": [...], "page": 1, "page_size": 20, "total": 134}`.
- **`degraded`:** an array present on search and answer responses, empty when everything worked. Possible values:
  - `rerank`: the reranker was skipped or timed out, so the fused order is returned;
  - `semantic`: the ML service or Qdrant was unavailable, so the Postgres full-text fallback was used;
  - `generation`: the LLM was unavailable (answer only).

---

## 2. Shared objects

**DocumentRef**
```json
{
  "doc_id": "K1500000414",
  "title": "Трудовой кодекс Республики Казахстан",
  "short_title": "Трудовой кодекс РК",
  "doc_type": "code",
  "number": "414-V",
  "adopted_date": "2015-11-23",
  "revision_date": "2026-01-01",
  "status": "in_force",
  "url": "https://adilet.zan.kz/rus/docs/K1500000414"
}
```
- `doc_type` is one of `code | law | decree | resolution | order | other`.
- `status` is one of `in_force | repealed | not_yet_in_force`.

**ArticleRef**
```json
{
  "article_id": "K1500000414:ru:a113",
  "unit_type": "article",
  "number": "113",
  "title": "Сроки, место и порядок выплаты заработной платы",
  "section_title": "…",
  "chapter_title": "…",
  "unit_status": "in_force",
  "has_amendments": true,
  "url": "https://adilet.zan.kz/rus/docs/K1500000414#z…"
}
```
- `unit_type` is one of `article | paragraph | chapter | preamble | annex`.
- `unit_status` is one of `in_force | excluded`.
- `url` points to the article anchor when one is known, otherwise to the document.

**SearchResult**
```json
{
  "rank": 1,
  "article": "ArticleRef",
  "doc": "DocumentRef",
  "chunk_id": "K1500000414:ru:a113:c0",
  "lang": "ru",
  "score": 0.91,
  "score_type": "rerank",
  "snippet": "…работодатель выплачивает заработную плату не реже одного раза в месяц…",
  "highlights": [{"start": 1, "end": 13}]
}
```
- `score_type` is one of `rerank | fusion | fts`.
- `snippet` is at most 300 chars: the passage of the best chunk most related to the query.
- `highlights` are character offsets into `snippet`; the array may be empty.

---

## 3. Public endpoints

### `POST /search`

Request:
```json
{
  "query": "Ответственность работодателя за задержку зарплаты",
  "lang": "auto",
  "mode": "hybrid",
  "top_k": 10,
  "filters": {
    "doc_types": [],
    "doc_ids": [],
    "in_force_only": true,
    "date_from": null,
    "date_to": null
  }
}
```

**`query`.** 1–500 chars after trimming.

**`lang`.** One of `auto | ru | kk`. With `auto`, the language is `kk` if the query contains any of `ә ғ қ ң ө ұ ү һ і` (either case), otherwise `ru`. Search is restricted to the resolved language.

**`mode`.**
- `hybrid` (default): dense + sparse → fusion → rerank.
- `semantic`: dense → rerank.
- `keyword`: sparse/BM25 only, no rerank. This stands in for classic keyword search and is used by the compare page.

**`top_k`.** 1–50, default 10.

**`filters`.**
- `in_force_only` defaults to `true`, meaning the act is in force **and** the article is not excluded.
- `date_from` / `date_to` filter on the act's adoption date.
- Empty arrays mean "no filter".

Response `200`:
```json
{
  "query_id": "5f0c2a9e-3b1d-4c8e-9a47-2d6f8e1b0c3a",
  "query": "Ответственность работодателя за задержку зарплаты",
  "lang": "ru",
  "mode": "hybrid",
  "results": ["SearchResult", "…"],
  "total_candidates": 87,
  "degraded": [],
  "timing_ms": {"embed": 41, "retrieve": 18, "fuse": 1, "rerank": 312, "total": 402},
  "pipeline_version": "1.0.0"
}
```
- There is one result per article (its best chunk).
- `results: []` is a valid answer, not an error.
- A `timing_ms` key may be missing if that stage did not run.

### `POST /answer` (response is `text/event-stream`)

The request body is the same as `/search`, plus `"context_top_k": 5` (range 1–8). Validation errors are returned as a normal JSON `422` before any stream starts.

Events, in order:

1. **`sources`** (sent once):
   ```
   event: sources
   data: {"query_id": "5f0c2a9e-3b1d-4c8e-9a47-2d6f8e1b0c3a", "lang": "ru", "sources": [{"ref": 1, "article": ArticleRef, "doc": DocumentRef, "snippet": "…"}], "degraded": []}
   ```
2. **`token`** (sent many times):
   ```
   event: token
   data: {"text": "Работодатель обязан "}
   ```
3. **`done`** (sent once):
   ```
   event: done
   data: {"answer_id": "b7e4d1c2-8f3a-4e6b-9d05-1a2c3e4f5a6b", "text": "<final text>", "citations": [1, 3], "invalid_citations_removed": 0, "grounded": true, "finish_reason": "stop", "timing_ms": {"search": 420, "ttft": 1900, "total": 6100}, "pipeline_version": "1.0.0"}
   ```
4. **`error`** (sent instead of `done` if something fails after the stream started):
   ```
   event: error
   data: {"code": "generation_unavailable", "message": "…"}
   ```
   Sources that were already sent stay valid.

Rules:
- **Citations.** A citation marker is `[n]`, where `n` is a source `ref`. The model may write `[1, 3]` or `[1][3]`; the backend normalises both to `[1][3]` and removes markers that do not match a source.
- **Final text.** `done.text` is authoritative. The client should replace the streamed text with it.
- **`grounded`** is `false` when the model states that the sources do not answer the question, or when no valid citation remains.
- **Zero results.** If search finds nothing, the stream is `sources` with an empty list, then `done` with `grounded: false`, `finish_reason: "no_results"` and a fixed "not found" message in the query's language. The LLM is not called.
- **Heartbeat.** The server sends a comment line `: ping` every 15 s.
- **Line endings.** Event lines may end with `\r\n` or `\n` (both are valid SSE); parse both.
- **Errors before the stream.** Validation errors (422) and search failures (503 `upstream_unavailable`, e.g. no index) are normal JSON error responses; no stream is opened.
- **Disconnect.** If the client disconnects, generation is cancelled.
- **Schemas.** `openapi.json` publishes the four payloads as `SourcesEvent`, `TokenEvent`, `DoneEvent` and `ErrorEvent`, linked from the `/answer` 200 response under `x-sse-events`.

### `GET /documents`

Query parameters: `lang` (required, `ru|kk`), `doc_type`, `q` (substring match on the title), `page`, `page_size`.

Returns a paginated list of `DocumentRef` objects, each with an extra `article_count`.

### `GET /documents/{doc_id}?lang=ru`

`lang` is required (`ru|kk`). Returns `404 not_found` for an unknown (`doc_id`, `lang`). Returns a `DocumentRef` plus `"toc"`: an array of `{article_id, unit_type, number, title, section_title, chapter_title, unit_status}` in document order.

### `GET /articles/{article_id}`

```json
{
  "article": "ArticleRef",
  "doc": "DocumentRef",
  "lang": "ru",
  "text": "<full verbatim article text>",
  "amendment_notes": ["Сноска. Статья 113 с изменениями, внесенными …"],
  "parallel_article_id": "K1500000414:kk:a113",
  "prev_article_id": "K1500000414:ru:a112",
  "next_article_id": "K1500000414:ru:a114"
}
```
Returns `404 not_found` for an unknown id. The `text` preserves line breaks and numbering.

### `POST /feedback`

```json
{"query_id": "5f0c2a9e-3b1d-4c8e-9a47-2d6f8e1b0c3a", "target": "result", "article_id": "K1500000414:ru:a113", "rating": 1, "comment": null}
```
- `target` is `result` (then `article_id` is required) or `answer` (then `article_id` is ignored).
- Unknown `query_id` → `404 not_found`.
- `rating` is `1` or `-1`.
- `comment` is at most 1000 chars.
- Returns `204`. A repeat for the same (session, query, target, article) overwrites the earlier feedback.

### `GET /health`

```json
{"status": "ok", "components": {"database": "ok", "qdrant": "ok", "ml_service": "ok", "llm": "unavailable"}, "pipeline_version": "1.0.0", "app_version": "0.3.0"}
```

| `status` | Meaning | HTTP |
|---|---|---|
| `ok` | everything works | 200 |
| `degraded` | search works but some component is down | 200 |
| `down` | search cannot work | 503 |

- Component values: `ok`, `degraded` (reachable, but some of its parts fail), `down` (unreachable or failing), `unavailable` (used for `llm`: not reachable or not configured).
- `status` is `down` when `database` is not `ok` (not even the full-text fallback can run), `degraded` when `qdrant` or `ml_service` is not `ok`, otherwise `ok`. `llm` is reported but does not change `status`, because it only serves `/answer`.
- `ml_service` is `ok` when the ML service's search models (embedder, sparse encoder, reranker) are all `ok`; its generator is reported as `llm`.
- `pipeline_version` is `null` until the model manifest has been loaded (the same applies to `/version`).

### `GET /version`

```json
{"app_version": "0.3.0", "git_sha": "a1b2c3d", "pipeline_version": "1.0.0", "index_collection": "legal_chunks__1.0.0"}
```
`index_collection` is the collection the `legal_chunks` alias points to, or `null` if no index has been built yet (or Qdrant is unreachable).

---

## 4. Admin endpoints (`Authorization: Bearer <JWT>`)

### `POST /admin/login`

Request: `{"username": "…", "password": "…"}`

Response: `{"access_token": "…", "token_type": "bearer", "expires_in": 28800}`. Wrong credentials return `401`.

### `GET /admin/stats?date_from=&date_to=`

Defaults to the last 7 days.

```json
{
  "date_from": "2026-11-01", "date_to": "2026-11-07",
  "totals": {"queries": 1240, "unique_sessions": 310, "answers": 402, "feedback_positive": 88, "feedback_negative": 17, "zero_result_queries": 31},
  "rates": {"zero_result_rate": 0.025, "satisfaction_rate": 0.838, "degraded_rate": 0.004},
  "latency_ms": {"search_p50": 380, "search_p95": 910, "answer_ttft_p50": 2100, "answer_ttft_p95": 3900},
  "by_day": [{"date": "2026-11-01", "queries": 150, "search_p95_ms": 870, "zero_result_rate": 0.02}],
  "by_lang": [{"lang": "ru", "queries": 1010}, {"lang": "kk", "queries": 230}],
  "by_mode": [{"mode": "hybrid", "queries": 1100}, {"mode": "keyword", "queries": 140}],
  "top_queries": [{"query": "…", "count": 12}],
  "top_zero_result_queries": [{"query": "…", "count": 4}]
}
```
- `satisfaction_rate` = positive / (positive + negative), or `null` if there is no feedback.
- `top_*` lists hold up to 20 items each, grouped by the normalised query (lower-cased, whitespace-collapsed).

### `GET /admin/queries`

Filters: `page`, `page_size`, `q`, `lang`, `mode`, `zero_results` (bool), `feedback` (`positive|negative`), `degraded` (bool), `date_from`, `date_to`.

Returns a paginated list of:
```json
{"query_id": "5f0c2a9e-3b1d-4c8e-9a47-2d6f8e1b0c3a", "created_at": "2026-11-03T10:12:45Z", "query": "…", "lang": "ru", "mode": "hybrid", "result_count": 10, "top_article_id": "K1500000414:ru:a113", "search_ms": 402, "has_answer": true, "feedback": {"positive": 0, "negative": 1}, "degraded": []}
```

### `GET /admin/queries/{query_id}`

Returns the list item above plus:
```json
{
  "filters": {"doc_types": [], "doc_ids": [], "in_force_only": true, "date_from": null, "date_to": null},
  "top_k": 10,
  "results": [{"rank": 1, "article_id": "K1500000414:ru:a113", "title": "Сроки, место и порядок выплаты заработной платы", "doc_short_title": "Трудовой кодекс РК", "score": 0.91}],
  "timing_ms": {"embed": 41, "retrieve": 18, "fuse": 1, "rerank": 312, "total": 402},
  "answer": {"answer_id": "b7e4d1c2-8f3a-4e6b-9d05-1a2c3e4f5a6b", "text": "…", "citations": [1, 3], "grounded": true, "timing_ms": {"ttft": 1900, "total": 6100}},
  "feedback_items": [{"target": "result", "article_id": "K1500000414:ru:a113", "rating": -1, "comment": "…", "created_at": "2026-11-03T10:14:02Z"}],
  "pipeline_version": "1.0.0",
  "session_hash": "ab12…"
}
```
`answer` is `null` when no answer was generated.

### `GET /admin/queries/export`

Takes the same filters as `/admin/queries`. Returns `text/csv` (UTF-8 with BOM, so Excel opens Cyrillic correctly) with one row per query: `query_id, created_at, query, lang, mode, result_count, top_article_id, search_ms, has_answer, feedback_positive, feedback_negative, degraded`.

### `GET /admin/system`

```json
{
  "components": {"database": "ok", "qdrant": "ok", "ml_service": "ok", "llm": "ok"},
  "app_version": "0.3.0", "git_sha": "a1b2c3d", "uptime_s": 86400,
  "pipeline": {"pipeline_version": "1.0.0", "embedder": "adilet-embedder-ft@3f9a1c2", "reranker": "adilet-reranker-ft@77b0e41", "generator": "adilet-generator-qlora@q4_k_m", "index_compat_id": "e5ft-bm25ru-ch1"},
  "index": {"alias": "legal_chunks", "collection": "legal_chunks__1.0.0", "points": 15230, "documents": 16, "articles": 9800, "index_compat_id": "e5ft-bm25ru-ch1", "compatible": true, "last_job": "Job | null"}
}
```

### `POST /admin/reindex`

Request: `{"source": "processed", "use_precomputed_embeddings": true}`, where `source` is `processed | sample`.

Returns `202` with `{"job_id": "0c9d8e7f-6a5b-4c3d-8e2f-1a0b9c8d7e6f"}`. Returns `409 conflict` if a job is already running.

### `GET /admin/jobs/{job_id}`

Returns a **Job**:
```json
{"job_id": "0c9d8e7f-6a5b-4c3d-8e2f-1a0b9c8d7e6f", "kind": "reindex", "status": "running", "progress": 0.42, "message": "embedded 6400/15230 chunks", "created_at": "2026-11-05T09:00:00Z", "started_at": "2026-11-05T09:00:01Z", "finished_at": null}
```
`status` is one of `queued | running | succeeded | failed`.

---

## 5. Limits and versioning

- **Default rate limits** (configurable), counted per session + IP:

  | Endpoint | Limit |
  |---|---|
  | `/search` | 60/min |
  | `/answer` | 10/min |
  | `/admin/login` | 5/min |

  Exceeding a limit returns `429` with `Retry-After`. Server-to-server callers with a valid `X-API-Key` get higher limits.
- `/metrics` (Prometheus) is served by the backend at the root path. It is not exposed through Caddy.
- **Breaking changes** need Frontend's acknowledgement through `contracts/CHANGELOG.md`. Additive changes (a new optional field or a new endpoint) need only a CHANGELOG entry.
