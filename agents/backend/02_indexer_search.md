# BE-02: Indexer, search pipeline, documents and articles (week 2)

**Goal: G1, the walking skeleton.** A real query over real sample data goes through the real API and the real zero-shot models, and returns sensible Labor Code articles.

Inputs from ML (check `docs/status/ml.md`):
- `data/sample/` (Parquet files);
- the `ml-service` compose snippet;
- `model_manifest.json`;
- `contracts/fixtures/fusion_cases.json`.

If any of them is missing, keep going with the fake ML service and add a request to your status file.

## Tasks

1. **Wire the ML services.** Add `ml-service` and `llm` to `docker-compose.yml` from ML's snippet (under the `ml` profile). Load the manifest per `MANIFEST_SOURCE=file|service`.

2. **Indexer CLI.**

   ```
   python -m indexer --data-dir data/sample --manifest ml/models/model_manifest.json [--embeddings path.parquet] [--batch-size 64] [--no-switch]
   ```

   It does the following, in order:
   - Validates the Parquet files against the columns in `data_schema.md` and fails loudly on a mismatch.
   - Upserts `documents` and `articles` into Postgres. It is idempotent: unchanged rows are skipped via `content_hash`.
   - Creates the collection `legal_chunks__{pipeline_version}` per `data_schema.md` §8: named `dense` and `sparse` vectors, HNSW parameters, `modifier: idf`, payload indexes.
   - Gets vectors, either from the precomputed embeddings file if given (checking that its `pipeline_version` matches) or from `ml-service /embed` (kind = `passage`) in batches, with retries and progress logging.
   - Upserts the points (`uuid5(chunk_id)`), checks that the point count equals the chunk count, records `index_state` (including `index_compat_id`), and then **atomically switches the alias** `legal_chunks` (unless `--no-switch` is set).
   - Writes an `index_jobs` row with its progress, so the BE-04 admin reindex can reuse the same code.

3. **Search service**, following `contracts/api.md` `/search` and `ml_service.md` §2:
   - **Validate:** 1–500 chars after trimming; `top_k` 1–50.
   - **Detect the language** with the contract rule (Kazakh-specific letters), in `services/lang.py`.
   - **Embed:** `/embed` with kind = `query`. Request only the vector types the mode needs.
   - **Retrieve:** a dense search and a sparse search **in parallel** (`asyncio.gather`) on the alias, using `dense_limit`/`sparse_limit` from the manifest. The filters (lang, doc_ids, doc_types, in-force, adoption-date range) become a Qdrant payload filter.
   - **Fuse:** implement `services/fusion.py` exactly per contract §2. Unit tests must pass on `contracts/fixtures/fusion_cases.json`, plus your own edge cases.
   - **Rerank:** `/rerank` on the top `rerank_top_n` articles, using the best chunk's `text_for_embedding`.
   - **Assemble** the top-k:
     - fetch article and document metadata from Postgres in one query;
     - build `snippet` (≤ 300 chars: the sentence window of the best chunk with the most query-term overlap);
     - compute `highlights` (offsets of query terms or stems found in the snippet; an empty list is fine);
     - fill in `score_type`, `timing_ms` per stage and `pipeline_version`.
   - **Modes:** `semantic` and `keyword` as defined in the contract.
   - **Compatibility check:** if `index_state.index_compat_id` ≠ the manifest's, skip dense search and add `degraded: ["semantic"]` (the full-text fallback comes in BE-04; for now return an `upstream_unavailable` error).

4. **Endpoints:** `POST /search`, `GET /documents`, `GET /documents/{doc_id}`, `GET /articles/{article_id}` (prev/next come from `unit_order`; `parallel_article_id` comes from the data).

5. **Basic logging.** Write a `query_logs` row for each search in the background: query, lang, mode, filters, top_k, result article ids + scores, timings, degraded, zero_results, pipeline_version, and `session_hash` (salted SHA-256 of `X-Session-Id`). It is extended in BE-03.

6. **Tests.**
   - **Unit:** fusion (the fixture), language detection, filter building, snippet/highlight building, mode handling, timeouts → degraded.
   - **Integration** (compose test profile with postgres, qdrant and fake-ml):
     - index `data/sample` with the fake vectors;
     - `/search` returns 200 with the contract shape;
     - the filters work;
     - `/articles/{id}` round-trips.
   - **Opt-in `@pytest.mark.ml` test** against the real `ml-service` v0: «Основания расторжения трудового договора» returns Labor Code articles in the top 5.

## Acceptance criteria (G1)

- [ ] With `--profile ml`, `python -m indexer --data-dir data/sample` succeeds, and the alias points to the new collection.
- [ ] Each of the three TOR example queries returns plausible articles. Paste the top 3 for each into the status file.
- [ ] Measure `/search` on the dev machine (single user, 20 queries) and record the p50/p95 per stage in the status file.
- [ ] `openapi.json` is regenerated if anything changed, and Frontend is told.
