# ML-02: ml-service v0 (walking skeleton) and LLM serving (week 2)

**Backend is already waiting for this phase** (it finished BE-03 against its fake ML service). Before you start, read the open requests to ML in `docs/status/backend.md`; this phase answers all of them. They are summarised in tasks 4–6 and 10 below.

**Goal:** by the end of week 2 the Backend can call real zero-shot models through the contract. Quality comes later. The **interface must already have its final shape.**

## Tasks

1. **The service.** Implement `ml/serving/`, a FastAPI app that follows `contracts/ml_service.md` exactly: `GET /health`, `GET /version`, `GET /metrics`, `POST /embed`, `POST /rerank`, `POST /generate` (SSE stream and non-stream). Errors use the contract's error shape and propagate `X-Request-Id`.

2. **Model loading.**
   - The service reads `ml/models/model_manifest.json` (path from env `MODEL_MANIFEST_PATH`).
   - Weights go to `MODEL_CACHE_DIR` (a mounted volume). `ml/scripts/fetch_models.py` downloads the pinned revisions. **Weights are never baked into the image.**
   - Load models once at startup. `/health` reports `down` until they are loaded.

3. **v0 components** (`pipeline_version` 0.1.0):
   - **Embedder:** `intfloat/multilingual-e5-base`, zero-shot. Apply the `query: ` / `passage: ` prefixes inside the service, normalise the vectors, and batch internally.
   - **Sparse encoder:** BM25 term weights.
     - RU: Snowball stemming + stopwords. KK: lowercase + a simple tokeniser for now; note it as a known limitation.
     - Tokens map to stable uint32 indices: a fixed hash or a saved vocabulary.
     - Passages get BM25 TF saturation with `k1`, `b` and `avgdl` from the manifest. Queries get 1.0 per unique term.
     - IDF is applied by Qdrant (`qdrant_idf_modifier: true`). Use the same tokeniser for passages and queries.
     - Save the artifact (vocabulary/params) with a version that feeds `index_compat_id`.
   - **Reranker:** a small multilingual cross-encoder, e.g. `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`. Verify that it loads and measure its CPU latency on 30 candidates.
   - **Generator:**
     - Calls an OpenAI-compatible endpoint (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`).
     - Provide the `llm` service: the llama.cpp server image plus a GGUF (Q4_K_M) of an instruct model with good Russian, small enough for CPU (try ~3B first and record its speed).
     - Document in `ml/serving/README.md` how to point at an external GPU endpoint instead.

4. **Prompt template `ml/prompts/answer_v1.md`** (a system part and a user part). Its rules:
   - answer **only** from the numbered sources;
   - put `[n]` after every claim;
   - reply in the question's language;
   - if the sources do not answer the question, say so plainly and do not guess;
   - no personal legal advice, no invented article numbers;
   - at most ~200 words.

   The service fills the template from the `/generate` sources.

   **Refusal phrase (agreed with Backend).** When the sources don't answer the question, the model must use one fixed phrase per language. Backend's `grounded` flag detects these exact phrases (case- and whitespace-insensitive; the list is in `backend/app/services/citations.py`):
   - RU: «в предоставленных источниках нет ответа» (also accepted: «источники не содержат ответа», «не могу ответить на основании предоставленных источников»);
   - KK: «берілген дереккөздерде жауап жоқ».

   Use one of these. If you need a different phrase, ask Backend through your status file before you ship. The SFT data in ML-04 must use the same phrases. Ask a native speaker to check the KK phrase.

   **What `/generate` receives from Backend:**
   - `stream: true`, `max_tokens` 512, `temperature` 0.1, ≤ 8 sources;
   - each source text is cut at a paragraph boundary to `retrieval.max_chars_per_context`;
   - titles look like `«{short_title}. Статья {N}. {title}»` / `«{short_title}. {N}-бап. {title}»`.

   Backend waits up to `ANSWER_TIMEOUT_S` (90 s) per chunk and in total. If CPU TTFT needs more, tell Backend.

5. **Fusion fixture.**
   - Implement `adilet_ml.retrieval.fusion.rrf` (the contract §2 algorithm, including collapse to articles).
   - Write `contracts/fixtures/fusion_cases.json` with at least 6 cases:
     - ties;
     - chunks present in only one list;
     - several chunks of one article;
     - unequal weights;
     - empty lists;
     - `keyword` mode.

   The backend tests its own implementation against this file. **Use the format Backend proposed** in `docs/status/backend.md`, because its test `backend/tests/unit/test_fusion.py` runs it automatically:

   ```json
   {"cases": [{"name": "…", "mode": "hybrid|semantic|keyword",
               "params": {"rrf_k": 60, "weights": {"dense": 1.0, "sparse": 1.0}, "dense_limit": 50, "sparse_limit": 50, "rerank_top_n": 30},
               "dense": ["<chunk_id>", "…"], "sparse": ["<chunk_id>", "…"],
               "rerank_scores": {"<article_id>": 7.2},
               "expected": [{"article_id": "…", "best_chunk_id": "…", "score": 0.0328}]}]}
   ```

   `dense_limit`, `sparse_limit`, `rerank_top_n`, `rerank_scores`, `best_chunk_id` and `score` are optional. Use real-looking chunk ids (`{doc_id}:{lang}:{unit_key}:c{n}`), not `c1`.

6. **Packaging.**
   - `ml/serving/Dockerfile`: CPU-only torch wheels, non-root user, a healthcheck, `MODEL_CACHE_DIR` as a volume.
   - Put a ready-to-paste compose snippet for `ml-service` (port 8001) and `llm` (port 8002) in your status file: images/build, env, volumes, healthchecks, resource limits. Backend owns `docker-compose.yml` and will add them under the `ml` profile.
   - Backend's dev stack needs nothing else from you: it already runs Postgres, Qdrant (gRPC on 6334) and a fake ML service. On Windows a native PostgreSQL may hold port 5432, so the stack uses `POSTGRES_PORT=55432`.

7. **Manifest and docs.** Write `ml/models/model_manifest.json` v0.1.0 (the contract §3 schema, revisions pinned to commit SHAs) and `ml/serving/README.md` with curl examples for every endpoint.

8. **Tests:**
   - request/response schema tests;
   - prefix handling;
   - sparse encoder determinism (same input gives the same output, and indices are stable across processes);
   - SSE event format;
   - `/generate` with a mocked LLM;
   - `/health` before and after loading;
   - the fusion implementation against the fixture.

9. **Benchmarks** (`ml/scripts/bench_latency.py`). On CPU, with the threads limited to 4, record p50/p95 in your status table for:
   - `/embed` with 1 query;
   - `/embed` with 64 passages;
   - `/rerank` with 30 candidates;
   - `/generate` TTFT and tokens/s.

10. **Answer Backend's open data-schema questions** (CHANGELOG 2026-10-08 BE-02, decision D-015). Confirm or object in `contracts/CHANGELOG.md` (and `data_schema.md` §8 if you accept):
    - a same-version rebuild goes into a timestamped collection `legal_chunks__{pipeline_version}__{YYYYMMDDHHMMSS}`, and old collections are kept for rollback;
    - the backend copies the document's `corpus_version` onto each article row (`articles.parquet` has no such column).

## Acceptance criteria

- [ ] `docker build` and run work, and every curl example in `ml/serving/README.md` succeeds. `/version` returns the manifest.
- [ ] The fusion fixture is committed and its tests pass.
- [ ] Latency numbers are in the status file. If `/embed` or `/rerank` already exceed the contract budget, say so and propose a fix.
- [ ] Backend has been told the image name, env vars, compose snippet and measured latencies.

## Also start now (human-heavy, long lead time)

Draft the first 100 gold query candidates for ML-03 Part A and give them to the humans for editing. Labelling takes calendar time.
