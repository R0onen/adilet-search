# BE-03: Streamed RAG answer, feedback, full query logging (week 3)

**Goal: G2.** `POST /answer` streams a grounded answer with validated citations end to end. Feedback and logs are complete. The full Tier-1 corpus is indexed.

## Tasks

1. **The `POST /answer` stream** (sse-starlette, `text/event-stream`), exactly as in `contracts/api.md`:
   1. Validate the body (a JSON 422 is returned before the stream starts).
   2. Run the shared search pipeline (do not duplicate the code). Take the top `context_top_k` articles and load their **full** text from Postgres. Truncate each to `max_chars_per_context`, cutting at a paragraph boundary.
   3. Emit `sources` **immediately**, with `ref` 1..n.
   4. If there are zero results, emit `done` with `grounded: false` and the fixed "not found" text in the query language. Do not call the LLM.
   5. Call `ml-service /generate` (stream) and relay each `token` event as it arrives.
   6. Post-process the citations with `services/citations.py`:
      - normalise `[1, 3]`, `[1,3]` and `[1][3]` to `[1][3]`;
      - drop markers whose number is not a source `ref`, and count them in `invalid_citations_removed`;
      - collect `citations` (the sorted unique refs);
      - set `grounded`: false if no valid citation remains or the model's refusal phrase is detected (agree the phrase list with ML: it lives in the prompt template).
   7. Emit `done` with the authoritative final `text`, the timings (`search`, `ttft`, `total`) and `pipeline_version`. Persist the answer, linked to `query_id`.
   8. **Failures:**
      - the LLM is unavailable or times out (`ANSWER_TIMEOUT_S`, default 90) → emit `error` with code `generation_unavailable`, after the sources;
      - the client disconnects → cancel the upstream request and log it as `cancelled`.
   9. Send a heartbeat `: ping` every 15 s.

2. **`POST /feedback`** per the contract: validation (`article_id` is required for `target=result`; the `query_id` must exist), and an upsert keyed on (session_hash, query_id, target, article_id). Returns 204.

3. **Complete query logging.** In addition to the BE-02 fields, record: user-agent family (not the full UA), `has_answer`, answer timings, `degraded`, error codes, and the `client` (`web` / `api-key` / `unknown`). Add an IP **hash** (salted, rotated by a secret) only if needed for rate limiting; never store raw IPs.

4. **Full corpus.** When ML announces the full Tier-1 corpus, download it with ML's script, reindex (a new collection, then the alias switch), and record the counts and duration in the status file.

5. **Tests.**
   - **Unit tests for the citation parser**, with cases such as:
     - `[1]`, `[1, 2]`, `[1][2]`, `[12]` when there are 5 sources;
     - `[0]`;
     - markers inside words;
     - Kazakh text;
     - no markers at all;
     - the refusal phrase.
   - **SSE tests** with an httpx streaming client against the fake ML: the event order, the JSON in each event, `done.text` equal to the cleaned text, `error` after `sources` when `FAKE_ML_FAIL=generate`, and zero results giving `done` with no LLM call.
   - **Disconnect test:** the upstream request is cancelled.
   - **Feedback tests:** validation, upsert, unknown `query_id` → 404.

## Acceptance criteria (G2)

- [ ] In the dev stack with the real ML v0, all three TOR queries stream answers with `[n]` citations that point to the right sources.
- [ ] Every SSE test passes. `openapi.json` documents `/answer` (the request body and the `text/event-stream` response with the event schemas described).
- [ ] The full Tier-1 corpus is indexed (counts in the status file).
- [ ] Frontend is told: "answer and feedback are live; SSE heartbeat is 15 s; `done.text` replaces the streamed text".
